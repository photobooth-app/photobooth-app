"""
Picamera2 backend implementation

"""

import dataclasses
import io
import logging
import uuid
from pathlib import Path
from threading import Condition, Event

from libcamera import Transform, controls
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, MJPEGEncoder, Quality
from picamera2.outputs import FfmpegOutput, FileOutput

from ...utils.stoppablethread import StoppableThread
from ..config import appconfig
from ..config.groups.backends import GroupBackendPicamera2
from .abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)


class Picamera2Backend(AbstractBackend):
    """
    The backend implementation using picamera2
    """

    @dataclasses.dataclass
    class PicamHiresData:
        """
        bundle data bytes and it's condition.
        1) save some instance attributes and
        2) bundle as it makes sense
        """

        # jpeg data as bytes
        data: bytes = None
        # signal to producer that requesting thread is ready to be notified
        request_hires_still: Event = None
        # condition when frame is avail
        condition: Condition = None

    class PicamLoresData(io.BufferedIOBase):
        """Lores data class used for streaming.
        Used in hardware accelerated MJPEGEncoder

        Args:
            io (_type_): _description_
        """

        def __init__(self):
            self.frame = None
            self.condition = Condition()

        def write(self, buf):
            with self.condition:
                self.frame = buf
                self.condition.notify_all()

    def __init__(self, config: GroupBackendPicamera2):
        self._config: GroupBackendPicamera2 = config
        super().__init__()
        # public props (defined in abstract class also)
        self._failing_wait_for_lores_image_is_error = True  # missing lores images is automatically considered as error

        # private props
        self._picamera2: Picamera2 = None

        # lores and hires data output
        self._lores_data: __class__.PicamLoresData = None
        self._hires_data: __class__.PicamHiresData = None

        # video related variables. picamera2 uses local recording implementation and overrides abstractbackend
        self._video_recorded_videofilepath = None
        self._video_encoder = None
        self._video_output = None

        # worker threads
        self._worker_thread: StoppableThread = None

        self._capture_config = None
        self._preview_config = None
        self._current_config = None
        self._last_config = None

    def _device_start(self):
        """To start the backend, configure picamera2"""
        self._lores_data: __class__.PicamLoresData = __class__.PicamLoresData()

        self._hires_data: __class__.PicamHiresData = __class__.PicamHiresData(data=None, request_hires_still=Event(), condition=Condition())

        # https://github.com/raspberrypi/picamera2/issues/576
        if self._picamera2:
            self._picamera2.close()
            del self._picamera2

        self._picamera2: Picamera2 = Picamera2(camera_num=self._config.camera_num)

        # config HQ mode (used for picture capture and live preview on countdown)
        self._capture_config = self._picamera2.create_still_configuration(
            main={
                "size": (
                    self._config.CAPTURE_CAM_RESOLUTION_WIDTH,
                    self._config.CAPTURE_CAM_RESOLUTION_HEIGHT,
                )
            },
            lores={
                "size": (
                    self._config.LIVEVIEW_RESOLUTION_WIDTH,
                    self._config.LIVEVIEW_RESOLUTION_HEIGHT,
                )
            },
            encode="lores",
            buffer_count=3,
            display="lores",
            transform=Transform(
                hflip=self._config.CAMERA_TRANSFORM_HFLIP,
                vflip=self._config.CAMERA_TRANSFORM_VFLIP,
            ),
        )

        # config preview mode (used for permanent live view)
        self._preview_config = self._picamera2.create_video_configuration(
            main={
                "size": (
                    self._config.PREVIEW_CAM_RESOLUTION_WIDTH,
                    self._config.PREVIEW_CAM_RESOLUTION_HEIGHT,
                )
            },
            lores={
                "size": (
                    self._config.LIVEVIEW_RESOLUTION_WIDTH,
                    self._config.LIVEVIEW_RESOLUTION_HEIGHT,
                )
            },
            encode="lores",
            buffer_count=3,
            display="lores",
            transform=Transform(
                hflip=self._config.CAMERA_TRANSFORM_HFLIP,
                vflip=self._config.CAMERA_TRANSFORM_VFLIP,
            ),
        )

        # select preview mode on init
        self._on_configure_optimized_for_idle()

        # configure; camera needs to be stopped before
        self._picamera2.configure(self._current_config)

        # capture_file image quality
        self._picamera2.options["quality"] = self._config.original_still_quality

        logger.info(f"camera_config: {self._picamera2.camera_config}")
        logger.info(f"camera_controls: {self._picamera2.camera_controls}")
        logger.info(f"controls: {self._picamera2.controls}")

        self.set_ae_exposure(self._config.AE_EXPOSURE_MODE)
        logger.info(f"stream quality {Quality[self._config.videostream_quality]=}")

        # start encoder
        self._picamera2.start_encoder(MJPEGEncoder(), FileOutput(self._lores_data), quality=Quality[self._config.videostream_quality])

        # start camera
        self._picamera2.start()

        self._worker_thread = StoppableThread(name="_picamera2_worker_thread", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        # wait until threads are up and deliver images actually. raises exceptions if fails after several retries
        self._block_until_delivers_lores_images()

        self._init_autofocus()

        logger.debug(f"{self.__module__} started")

    def _device_stop(self):
        """To stop the FrameServer, first stop any client threads (that might be
        blocked in wait_for_frame), then call this stop method. Don't stop the
        Picamera2 object until the FrameServer has been stopped."""
        if self._worker_thread and self._worker_thread.is_alive():
            logger.debug("stopping")
            self._worker_thread.stop()
            logger.debug("stopped")
            self._worker_thread.join()
            logger.debug("joined")

        logger.debug("stop encoder")
        self._picamera2.stop_encoder()
        self._picamera2.stop()
        self._picamera2.close()  # need to close camera so it can be used by other processes also (or be started again)
        logger.debug("closed")

        logger.debug(f"{self.__module__} stopped,  {self._worker_thread.is_alive()=}")

    def _device_available(self) -> bool:
        """picameras are assumed to be available always for now"""
        return True

    def _wait_for_hq_image(self):
        """
        for other threads to receive a hq JPEG image
        mode switches are handled internally automatically, no separate trigger necessary
        this function blocks until frame is received
        raise TimeoutError if no frame was received
        """
        with self._hires_data.condition:
            self._hires_data.request_hires_still.set()

            if not self._hires_data.condition.wait(timeout=4):
                # wait returns true if timeout expired
                raise TimeoutError("timeout receiving frames")

        self._hires_data.request_hires_still.clear()
        return self._hires_data.data

    #
    # INTERNAL FUNCTIONS
    #
    @staticmethod
    def _round_none(value, digits):
        """
        function that returns None if value is None,
        otherwise round is applied and returned

        Args:
            value (_type_): _description_
            digits (_type_): _description_

        Returns:
            _type_: _description_
        """
        if value is None:
            return None

        return round(value, digits)

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=0.5):
                raise TimeoutError("timeout receiving frames")

            return self._lores_data.frame

    def start_recording(self):
        self._video_recorded_videofilepath = Path("tmp", f"{self.__class__.__name__}_{uuid.uuid4().hex}").with_suffix(".mp4")
        self._video_encoder = H264Encoder(appconfig.mediaprocessing.video_bitrate * 1000)  # bitrate in k in appconfig, so *1000
        self._video_output = FfmpegOutput(str(self._video_recorded_videofilepath))

        self._picamera2.start_encoder(self._video_encoder, self._video_output, name="lores")

        logger.info("picamera2 video encoder started")

    def stop_recording(self):
        if self._video_encoder and self._video_encoder.running:
            self._picamera2.stop_encoder(self._video_encoder)
            logger.info("picamera2 video encoder stopped")
        else:
            logger.info("no picamera2 video encoder active that could be stopped")

    def get_recorded_video(self) -> Path:
        if self._video_recorded_videofilepath is not None:
            out = self._video_recorded_videofilepath
            self._video_recorded_videofilepath = None

            return out
        else:
            raise FileNotFoundError("no recorded video avail! if start_recording was called, maybe capture video failed? pls check logs")

    def _on_configure_optimized_for_hq_capture(self):
        logger.debug("change to capture mode requested")
        self._last_config = self._current_config
        self._current_config = self._capture_config

    def _on_configure_optimized_for_idle(self):
        logger.debug("change to preview mode requested")
        self._last_config = self._current_config
        self._current_config = self._preview_config

    def set_ae_exposure(self, newmode):
        """_summary_

        Args:
            newmode (_type_): _description_
        """
        logger.info(f"set_ae_exposure, try to set to {newmode}")
        try:
            self._picamera2.set_controls({"AeExposureMode": newmode})
        except RuntimeError as exc:
            # catch runtimeerror and no reraise, can fail and being logged but continue.
            logger.error(f"set_ae_exposure failed! Mode {newmode} not available {exc}")

        logger.info(f"current picamera2.controls.get_libcamera_controls():" f"{self._picamera2.controls.get_libcamera_controls()}")

    def _switch_mode(self):
        logger.info("switch_mode invoked, stopping stream encoder, switch mode and restart encoder")

        self._picamera2.stop_encoder()
        self._last_config = self._current_config

        try:
            # in try-catch because switch_mode can fail if picamera cannot allocate buffers.
            # if this happens, backend signals error and shall be restarted.
            self._picamera2.switch_mode(self._current_config)
        except RuntimeError as exc:
            logger.exception(exc)
            logger.critical(f"error switching mode in picamera due to {exc}")
            # mark as faulty to restart.
            self.device_set_status_fault_flag()
        else:
            self._picamera2.start_encoder(MJPEGEncoder(), FileOutput(self._lores_data), quality=Quality[self._config.videostream_quality])
            logger.info("switchmode finished successfully")

    def _init_autofocus(self):
        """
        on start set autofocus to continuous if requested by config or
        auto and trigger regularly
        """

        try:
            self._picamera2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        except RuntimeError as exc:
            logger.critical(f"control not available on camera - autofocus not working properly {exc}")

        try:
            self._picamera2.set_controls({"AfSpeed": controls.AfSpeedEnum.Fast})
        except RuntimeError as exc:
            logger.info(f"control not available on all cameras - can ignore {exc}")

        logger.debug("autofocus set")

    #
    # INTERNAL IMAGE GENERATOR
    #

    def _worker_fun(self):
        while not self._worker_thread.stopped():  # repeat until stopped
            if self._hires_data.request_hires_still.is_set() is True and self._current_config != self._capture_config:
                # ensure cam is in capture quality mode even if there was no countdown
                # triggered beforehand usually there is a countdown, but this is to be safe
                logger.warning("force switchmode to capture config right before taking picture")
                self._on_configure_optimized_for_hq_capture()

            if (not self._current_config == self._last_config) and self._last_config is not None:
                if not self._worker_thread.stopped():
                    self._switch_mode()
                else:
                    logger.info("switch_mode ignored, because shutdown already requested")

            if self._hires_data.request_hires_still.is_set():
                # only capture one pic and return to lores streaming afterwards
                self._hires_data.request_hires_still.clear()
                # capture hq picture
                data = io.BytesIO()
                self._picamera2.capture_file(data, format="jpeg")
                self._hires_data.data = data.getbuffer()

                with self._hires_data.condition:
                    self._hires_data.condition.notify_all()

            # capture metadata blocks until new metadata is avail
            _metadata = self._picamera2.capture_metadata()

            # update backendstats (optional for backends, but this one has so many information that are easy to display)
            # exposure time needs math on a possibly None value, do it here separate because None/1000 raises an exception.
            exposure_time = _metadata.get("ExposureTime", None)
            exposure_time_ms_raw = exposure_time / 1000 if exposure_time is not None else None
            self._backendstats.exposure_time_ms = self._round_none(exposure_time_ms_raw, 1)
            self._backendstats.lens_position = self._round_none(_metadata.get("LensPosition", None), 2)
            self._backendstats.gain = self._round_none(_metadata.get("AnalogueGain", None), 1)
            self._backendstats.lux = self._round_none(_metadata.get("Lux", None), 1)
            self._backendstats.colour_temperature = _metadata.get("ColourTemperature", None)
            self._backendstats.sharpness = _metadata.get("FocusFoM", None)

        logger.info("_generate_images_fun left")
