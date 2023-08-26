"""
Picamera2 backend implementation

"""
import dataclasses
import io
import logging
import time
from threading import Condition, Event

from pymitter import EventEmitter

from photobooth.utils.stoppablethread import StoppableThread

from ...appconfig import AppConfig, EnumFocuserModule
from .abstractbackend import AbstractBackend, BackendStats
from .picamera2_libcamafcontinuous import Picamera2LibcamAfContinuous
from .picamera2_libcamafinterval import Picamera2LibcamAfInterval

try:
    from libcamera import Transform  # type: ignore
    from picamera2 import Picamera2  # type: ignore
    from picamera2.encoders import MJPEGEncoder, Quality  # type: ignore
    from picamera2.outputs import FileOutput  # type: ignore
except Exception as import_exc:
    raise OSError("picamera2/libcamera import error; check picamera2/libcamera installation") from import_exc

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
        request_ready: Event = None
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

    def __init__(self, evtbus: EventEmitter, config: AppConfig):
        super().__init__(evtbus, config)
        # public props (defined in abstract class also)
        self.metadata = {}

        # private props
        self._picamera2: Picamera2 = None
        self._autofocus_module = None

        self._count = 0
        self._fps = 0

        # lores and hires data output
        self._lores_data: __class__.PicamLoresData = None
        self._hires_data: __class__.PicamHiresData = None

        # worker threads
        self._generate_images_thread: StoppableThread = None
        self._stats_thread: StoppableThread = None

        self._capture_config = None
        self._preview_config = None
        self._current_config = None
        self._last_config = None

        if not self._config.backends.picamera2_focuser_module == EnumFocuserModule.NULL:
            logger.info(f"loading autofocus module: " f"picamera2_{self._config.backends.picamera2_focuser_module}")
            if self._config.backends.picamera2_focuser_module == EnumFocuserModule.LIBCAM_AF_CONTINUOUS:
                self._autofocus_module = Picamera2LibcamAfContinuous(self, evtbus=evtbus, config=config)
            elif self._config.backends.picamera2_focuser_module == EnumFocuserModule.LIBCAM_AF_INTERVAL:
                self._autofocus_module = Picamera2LibcamAfInterval(self, evtbus=evtbus, config=config)
            else:
                self._autofocus_module = None

        else:
            logger.info(
                "picamera2_focuser_module is disabled. " "Select a focuser module in config to enable autofocus."
            )

    def start(self):
        """To start the backend, configure picamera2"""
        self._lores_data: __class__.PicamLoresData = __class__.PicamLoresData()

        self._hires_data: __class__.PicamHiresData = __class__.PicamHiresData(
            data=None, request_ready=Event(), condition=Condition()
        )

        # https://github.com/raspberrypi/picamera2/issues/576
        if self._picamera2:
            self._picamera2.close()

        self._picamera2: Picamera2 = Picamera2()

        # config HQ mode (used for picture capture and live preview on countdown)
        self._capture_config = self._picamera2.create_still_configuration(
            main={
                "size": (
                    self._config.common.CAPTURE_CAM_RESOLUTION_WIDTH,
                    self._config.common.CAPTURE_CAM_RESOLUTION_HEIGHT,
                )
            },
            lores={
                "size": (
                    self._config.common.LIVEVIEW_RESOLUTION_WIDTH,
                    self._config.common.LIVEVIEW_RESOLUTION_HEIGHT,
                )
            },
            encode="lores",
            buffer_count=2,
            display="lores",
            transform=Transform(
                hflip=self._config.common.CAMERA_TRANSFORM_HFLIP,
                vflip=self._config.common.CAMERA_TRANSFORM_VFLIP,
            ),
        )

        # config preview mode (used for permanent live view)
        self._preview_config = self._picamera2.create_video_configuration(
            main={
                "size": (
                    self._config.common.PREVIEW_CAM_RESOLUTION_WIDTH,
                    self._config.common.PREVIEW_CAM_RESOLUTION_HEIGHT,
                )
            },
            lores={
                "size": (
                    self._config.common.LIVEVIEW_RESOLUTION_WIDTH,
                    self._config.common.LIVEVIEW_RESOLUTION_HEIGHT,
                )
            },
            encode="lores",
            buffer_count=2,
            display="lores",
            transform=Transform(
                hflip=self._config.common.CAMERA_TRANSFORM_HFLIP,
                vflip=self._config.common.CAMERA_TRANSFORM_VFLIP,
            ),
        )

        # activate preview mode on init
        self._on_preview_mode()

        # configure; camera needs to be stopped before
        self._picamera2.configure(self._current_config)

        # capture_file image quality
        self._picamera2.options["quality"] = self._config.common.HIRES_STILL_QUALITY

        logger.info(f"camera_config: {self._picamera2.camera_config}")
        logger.info(f"camera_controls: {self._picamera2.camera_controls}")
        logger.info(f"controls: {self._picamera2.controls}")

        self.set_ae_exposure(self._config.backends.picamera2_AE_EXPOSURE_MODE)
        logger.info(f"stream quality {Quality[self._config.backends.picamera2_stream_quality.name]=}")
        # start camera
        self._picamera2.start_encoder(
            MJPEGEncoder(),  # attention: GPU won't digest images wider than 4096 on a Pi 4.
            FileOutput(self._lores_data),
            quality=Quality[self._config.backends.picamera2_stream_quality.name],
        )
        self._picamera2.start()

        self._generate_images_thread = StoppableThread(
            name="_generateImagesThread", target=self._generate_images_fun, daemon=True
        )
        self._generate_images_thread.start()

        self._stats_thread = StoppableThread(name="_statsThread", target=self._stats_fun, daemon=True)
        self._stats_thread.start()

        if self._autofocus_module:
            self._autofocus_module.start()

        # block until startup completed, this ensures tests work well and backend for sure delivers images if requested
        remaining_retries = 10
        while True:
            with self._lores_data.condition:
                if self._lores_data.condition.wait(timeout=0.5):
                    break

                if remaining_retries < 0:
                    raise RuntimeError("failed to start up backend")

                remaining_retries -= 1
                logger.info("waiting for backend to start up...")

        logger.debug(f"{self.__module__} started")

    def stop(self):
        """To stop the FrameServer, first stop any client threads (that might be
        blocked in wait_for_frame), then call this stop method. Don't stop the
        Picamera2 object until the FrameServer has been stopped."""

        if self._autofocus_module:
            # autofocus module needs to stop their threads also for clean shutdown
            logger.info("stopping autofocus module")
            self._autofocus_module.stop()

        self._generate_images_thread.stop()
        self._stats_thread.stop()

        self._generate_images_thread.join()
        self._stats_thread.join()

        self._picamera2.stop_encoder()
        self._picamera2.stop()
        self._picamera2.close()  # need to close camera so it can be used by other processes also (or be started again)

        logger.debug(
            f"{self.__module__} stopped,  {self._generate_images_thread.is_alive()=},  {self._stats_thread.is_alive()=}"
        )

    def wait_for_hq_image(self):
        """
        for other threads to receive a hq JPEG image
        mode switches are handled internally automatically, no separate trigger necessary
        this function blocks until frame is received
        raise TimeoutError if no frame was received
        """
        with self._hires_data.condition:
            self._hires_data.request_ready.set()

            if not self._hires_data.condition.wait(timeout=4):
                # wait returns true if timeout expired
                raise TimeoutError("timeout receiving frames")

        self._hires_data.request_ready.clear()
        return self._hires_data.data

    def stats(self) -> BackendStats:
        # exposure time needs math on a possibly None value, do it here separate
        # because None/1000 raises an exception.
        exposure_time = self.metadata.get("ExposureTime", None)
        exposure_time_ms_raw = exposure_time / 1000 if exposure_time is not None else None
        return BackendStats(
            backend_name=__name__,
            fps=int(round(self._fps, 0)),
            exposure_time_ms=self._round_none(exposure_time_ms_raw, 1),
            lens_position=self._round_none(self.metadata.get("LensPosition", None), 2),
            gain=self._round_none(self.metadata.get("AnalogueGain", None), 1),
            lux=self._round_none(self.metadata.get("Lux", None), 1),
            colour_temperature=self.metadata.get("ColourTemperature", None),
            sharpness=self.metadata.get("FocusFoM", None),
        )

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
        if self._generate_images_thread.stopped():
            raise RuntimeError("shutdown already in progress, abort early")

        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=4):
                # wait returns true if timeout expired
                raise TimeoutError("timeout receiving frames")

            return self._lores_data.frame

    def _wait_for_lores_frame(self):
        """advanced autofocus currently not supported by this backend"""
        raise NotImplementedError()

    def _on_capture_mode(self):
        logger.debug("change to capture mode requested")
        self._last_config = self._current_config
        self._current_config = self._capture_config

    def _on_preview_mode(self):
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

        logger.info(
            f"current picamera2.controls.get_libcamera_controls():"
            f"{self._picamera2.controls.get_libcamera_controls()}"
        )

    def _switch_mode(self):
        logger.info("switch_mode invoked, stopping stream encoder, switch mode and restart encoder")
        # revisit later, maybe.
        # sometimes picamera2 got stuck calling switch_mode.
        # Seems it got better when changing from switch_mode to stop_encoder, stop, configure.
        # some further information here: https://github.com/raspberrypi/picamera2/issues/554
        self._picamera2.stop_encoder()
        self._last_config = self._current_config

        self._picamera2.switch_mode(self._current_config)

        self._picamera2.start_encoder(
            MJPEGEncoder(),
            FileOutput(self._lores_data),
            quality=Quality[self._config.backends.picamera2_stream_quality.name],
        )
        logger.info("switchmode finished successfully")

    #
    # INTERNAL IMAGE GENERATOR
    #

    def _stats_fun(self):
        # FPS = 1 / time to process loop
        last_calc_time = time.time()  # start time of the loop

        # to calc frames per second every second
        while not self._stats_thread.stopped():
            self._fps = round(
                float(self._count) / (time.time() - last_calc_time),
                1,
            )

            # reset
            self._count = 0
            last_calc_time = time.time()

            # thread wait
            time.sleep(0.2)

    def _generate_images_fun(self):
        while not self._generate_images_thread.stopped():  # repeat until stopped
            if self._hires_data.request_ready.is_set() is True and self._current_config != self._capture_config:
                # ensure cam is in capture quality mode even if there was no countdown
                # triggered beforehand usually there is a countdown, but this is to be safe
                logger.warning("force switchmode to capture config right before taking picture")
                self._on_capture_mode()

            if (not self._current_config == self._last_config) and self._last_config is not None:
                if not self._generate_images_thread.stopped():
                    self._switch_mode()
                else:
                    logger.info("switch_mode ignored, because shutdown already requested")

            if self._hires_data.request_ready.is_set():
                # only capture one pic and return to lores streaming afterwards
                self._hires_data.request_ready.clear()

                # ensure before shoot that no focus is active; module may decide how to handle or cancel current run
                if self._autofocus_module:
                    self._autofocus_module.ensure_focused()

                self._evtbus.emit("frameserver/onCapture")

                # capture hq picture
                data = io.BytesIO()
                self._picamera2.capture_file(data, format="jpeg")
                self._hires_data.data = data.getbuffer()

                self._evtbus.emit("frameserver/onCaptureFinished")

                with self._hires_data.condition:
                    self._hires_data.condition.notify_all()

                # switch back to preview mode
                self._on_preview_mode()

            # capture metadata blocks until new metadata is avail
            # fixme: following seems to block occasionally the switch_mode function. # pylint: disable=fixme
            # self.metadata = self._picamera2.capture_metadata()
            time.sleep(0.1)

            # counter to calc the fps
            # broken since capture_metadata is commented.
            # self._count += 1
        logger.info("_generate_images_fun left")
