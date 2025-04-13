"""
Picamera2 backend implementation

"""

import io
import logging
import uuid
from datetime import datetime
from pathlib import Path
from threading import Condition

from libcamera import controls  # type: ignore
from picamera2 import Picamera2  # type: ignore
from picamera2.allocators import PersistentAllocator  # type: ignore
from picamera2.encoders import H264Encoder, MJPEGEncoder, Quality  # type: ignore
from picamera2.outputs import FfmpegOutput, FileOutput  # type: ignore

from ...appconfig import appconfig
from ..config.groups.backends import GroupBackendPicamera2
from .abstractbackend import AbstractBackend

logger = logging.getLogger(__name__)


class PicamLoresData(io.BufferedIOBase):
    """Lores data class used for streaming.
    Used in hardware accelerated MJPEGEncoder

    Args:
        io (_type_): _description_
    """

    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf) -> int:
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

        return len(buf)


class Picamera2Backend(AbstractBackend):
    def __init__(self, config: GroupBackendPicamera2):
        self._config: GroupBackendPicamera2 = config
        super().__init__(orientation=config.orientation)

        # private props
        self._picamera2: Picamera2 | None = None
        self._mjpeg_encoder: MJPEGEncoder | None = None  # livestream encoder

        # lores and hires data output
        self._lores_data: PicamLoresData = PicamLoresData()

        # video related variables. picamera2 uses local recording implementation and overrides abstractbackend
        self._video_encoder = None
        self._video_output = None

        self._capture_config = None
        self._preview_config = None
        self._current_config = None
        self._last_config = None

    def start(self):
        super().start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        logger.debug(f"{self.__module__} stopped")

    def _load_default_tuning(self):
        with Picamera2(camera_num=self._config.camera_num) as cam:
            cp = cam.camera_properties
            fname = f"{cp['Model']}.json"

        return cam.load_tuning_file(fname)

    def _get_optimized_short_lowlight_tuning(self):
        """Every camera tuning file usually has at least "normal", "short" and "long" exposure modes.
        We modify the short one and switch to this exposure mode after turning on the camera.
        """
        tuning = self._load_default_tuning()
        algo = Picamera2.find_tuning_algo(tuning, "rpi.agc")

        # lower boundary at (100,1.0)
        # sequence raising exposure is raising shutter to 1000, then gain (here 1.0 also).
        # so it will continue raising shutter time to 2000, then gain to 2.0
        # 16000 == 1/63 is considered as reasonable max to capture stills from people in booth
        # so before 16000 is reached, the gain is first set to 14.0 (which is not max but very noisy already)
        # so during setup, one would try to achieve a shutter time in the range 2000-8000 with permanent lighting usually
        shutter = [100, 1000, 2000, 4000, 8000, 16000, 120000]
        gain = [1.0, 1.0, 2.0, 4.0, 8.0, 14.0, 14.0]

        if "channels" in algo:
            algo["channels"][0]["exposure_modes"]["short"] = {"shutter": shutter, "gain": gain}
        else:
            algo["exposure_modes"]["short"] = {"shutter": shutter, "gain": gain}

        return tuning

    def _wait_for_multicam_files(self) -> list[Path]:
        raise NotImplementedError("backend does not support multicam files")

    def _wait_for_still_file(self) -> Path:
        """
        for other threads to receive a hq JPEG image
        mode switches are handled internally automatically, no separate trigger necessary
        this function blocks until frame is received
        raise TimeoutError if no frame was received
        """
        with self._hires_data.condition:
            self._hires_data.request.set()

            if not self._hires_data.condition.wait(timeout=4):
                # wait returns true if timeout expired
                raise TimeoutError("timeout receiving frames")

            self._hires_data.request.clear()
            assert self._hires_data.filepath

            return self._hires_data.filepath

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

    def _wait_for_lores_image(self) -> bytes:
        """for other threads to receive a lores JPEG image"""

        assert self._lores_data

        self.pause_wait_for_lores_while_hires_capture()

        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=0.5):
                raise TimeoutError("timeout receiving frames")

            assert self._lores_data.frame
            return self._lores_data.frame

    def start_recording(self, video_framerate: int) -> Path:
        """picamera2 has local start_recording, which overrides the abstract class implementation in favor of local handling by picamera2"""
        assert self._picamera2

        video_recorded_videofilepath = Path("tmp", f"{self.__class__.__name__}_{uuid.uuid4().hex}").with_suffix(".mp4")
        self._video_encoder = H264Encoder(
            bitrate=appconfig.mediaprocessing.video_bitrate * 1000,  # bitrate in k in appconfig, so *1000
            framerate=video_framerate,
            profile="baseline" if appconfig.mediaprocessing.video_compatibility_mode else None,  # compat mode, baseline produces yuv420
        )
        self._video_output = FfmpegOutput(str(video_recorded_videofilepath))

        self._picamera2.start_encoder(self._video_encoder, self._video_output, name="lores")

        logger.info("picamera2 video encoder started")

        return video_recorded_videofilepath

    def stop_recording(self):
        if self._video_encoder and self._video_encoder.running:
            assert self._picamera2
            self._picamera2.stop_encoder(self._video_encoder)
            logger.info("picamera2 video encoder stopped")
        else:
            logger.info("no picamera2 video encoder active that could be stopped")

    def _on_configure_optimized_for_idle(self):
        logger.debug("change to preview mode requested")
        self._last_config = self._current_config
        self._current_config = self._preview_config

    def _on_configure_optimized_for_hq_preview(self):
        logger.debug("change to capture mode requested")
        self._last_config = self._current_config
        self._current_config = self._capture_config

    def _on_configure_optimized_for_hq_capture(self):
        """switch to hq capture is done during hq preview call already because it avoids switch delay on the actual capture"""
        pass

    def _switch_mode(self):
        assert self._picamera2
        logger.info("switch_mode invoked, stopping stream encoder, switch mode and restart encoder")

        self._picamera2.stop_encoder()
        self._last_config = self._current_config

        try:
            # in try-catch because switch_mode can fail if picamera cannot allocate buffers.
            # if this happens, backend signals error and shall be restarted.
            self._picamera2.switch_mode(self._current_config)
        except Exception as exc:
            logger.exception(exc)
            logger.critical(f"error switching mode in picamera due to {exc}")
            raise exc
        else:
            self._picamera2.start_encoder(self._mjpeg_encoder, FileOutput(self._lores_data), quality=Quality[self._config.videostream_quality])
            logger.info("switchmode finished successfully")

    def _init_autofocus(self):
        """
        on start set autofocus to continuous if requested by config or
        auto and trigger regularly
        """
        assert self._picamera2

        try:
            self._picamera2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        except RuntimeError as exc:
            logger.critical(f"control not available on camera - autofocus not working properly {exc}")

        try:
            self._picamera2.set_controls({"AfSpeed": controls.AfSpeedEnum.Fast})
        except RuntimeError as exc:
            logger.info(f"control not available on all cameras - can ignore {exc}")

        logger.debug("autofocus set")

    def setup_resource(self):
        logger.info("Connecting to resource...")

        if self._picamera2:
            logger.info("closing camera before starting to ensure it's available")
            self._picamera2.close()  # need to close camera so it can be used by other processes also (or be started again)

        tuning = None
        if self._config.optimized_lowlight_short_exposure:
            try:
                tuning = self._get_optimized_short_lowlight_tuning()
                logger.info("optimized tuningfile for low light loaded")
            except Exception as exc:
                logger.warning(f"error getting optimized lowlight tuning: {exc}")

        self._picamera2 = Picamera2(camera_num=self._config.camera_num, tuning=tuning, allocator=PersistentAllocator())
        assert self._picamera2

        # config HQ mode (used for picture capture and live preview on countdown)
        self._capture_config = self._picamera2.create_still_configuration(
            main={"size": (self._config.CAPTURE_CAM_RESOLUTION_WIDTH, self._config.CAPTURE_CAM_RESOLUTION_HEIGHT)},
            lores={"size": (self._config.LIVEVIEW_RESOLUTION_WIDTH, self._config.LIVEVIEW_RESOLUTION_HEIGHT)},
            encode="lores",
            buffer_count=3,
            display="lores",
            controls={"FrameRate": self._config.framerate_still_mode},
        )

        # config preview mode (used for permanent live view)
        self._preview_config = self._picamera2.create_video_configuration(
            main={"size": (self._config.PREVIEW_CAM_RESOLUTION_WIDTH, self._config.PREVIEW_CAM_RESOLUTION_HEIGHT)},
            lores={"size": (self._config.LIVEVIEW_RESOLUTION_WIDTH, self._config.LIVEVIEW_RESOLUTION_HEIGHT)},
            encode="lores",
            buffer_count=3,
            display="lores",
            controls={"FrameRate": self._config.framerate_video_mode},
        )

        # set preview mode on init
        self._current_config = self._preview_config

        # configure; camera needs to be stopped before
        self._picamera2.configure(self._current_config)

        # capture_file image quality
        self._picamera2.options["quality"] = self._config.original_still_quality

        logger.info(f"camera_config: {self._picamera2.camera_config}")
        logger.info(f"camera_controls: {self._picamera2.camera_controls}")
        logger.info(f"controls: {self._picamera2.controls}")
        logger.info(f"camera_properties: {self._picamera2.camera_properties}")

        if self._config.optimized_lowlight_short_exposure:
            self._picamera2.set_controls({"AeExposureMode": controls.AeExposureModeEnum.Short})
            logger.info(f"selected short exposure mode ({controls.AeExposureModeEnum.Short})")

        logger.info(f"stream quality {Quality[self._config.videostream_quality]=}")

        # start encoder
        self._mjpeg_encoder = MJPEGEncoder()
        assert self._mjpeg_encoder
        self._mjpeg_encoder.frame_skip_count = self._config.frame_skip_count
        self._picamera2.start_encoder(self._mjpeg_encoder, FileOutput(self._lores_data), quality=Quality[self._config.videostream_quality])

        # start camera
        self._picamera2.start()

        self._init_autofocus()

    def teardown_resource(self):
        logger.info("Disconnecting from resource...")

        # https://github.com/raspberrypi/picamera2/issues/576
        if self._picamera2:
            self._picamera2.stop_encoder()
            self._picamera2.stop()
            self._picamera2.close()  # need to close camera so it can be used by other processes also (or be started again)

    def run_service(self):
        logger.info("Running service logic...")
        assert self._picamera2

        _metadata = None

        while not self._stop_event.is_set():  # repeat until stopped
            if self._hires_data.request.is_set() is True and self._current_config != self._capture_config:
                # ensure cam is in capture quality mode even if there was no countdown
                # triggered beforehand usually there is a countdown, but this is to be safe
                logger.warning("force switchmode to capture config right before taking picture")
                self._on_configure_optimized_for_hq_capture()

            if (not self._current_config == self._last_config) and self._last_config is not None:
                if not self._stop_event.is_set():
                    self._switch_mode()
                else:
                    logger.info("switch_mode ignored, because shutdown already requested")

            if self._hires_data.request.is_set():
                # only capture one pic and return to lores streaming afterwards
                self._hires_data.request.clear()

                # capture hq picture
                with self._picamera2.captured_request(wait=1.5) as request:
                    # call captured_request instead direct call to capture_file because it seems
                    # the get_metadata leaks CmaMemory otherwise. Reference:
                    # https://github.com/raspberrypi/picamera2/issues/1125#issuecomment-2387829290
                    filepath = Path("tmp", f"picamera2_{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')}.jpg")
                    request.save("main", filepath)  # type: ignore

                    _metadata = request.get_metadata()  # type: ignore

                    self._hires_data.filepath = filepath

                with self._hires_data.condition:
                    self._hires_data.condition.notify_all()
            else:
                # capture metadata blocks until new metadata is avail
                try:
                    _metadata = self._picamera2.capture_metadata(wait=1.5)
                    # waiting for only 1.5s instead indefinite might cover underlying issues with the camera system but prevents the app from
                    # stalling
                except TimeoutError as exc:
                    # if camera runs out of Cma during switch_config, the camera stops delivering images and so also no metadata.
                    # the supervisor thread detects that no images come in and would try to restarting the picamera2 backend to recover.
                    # wait=1.5 was added to avoid stalling the _worker_fun thread raising a timeout after 1.5 seconds without images/metadata latest.
                    # inform about the error, no need to reraise the issue actually again.

                    # stop device requested by leaving worker loop, so backend can restart
                    raise RuntimeError(f"camera stopped delivering frames, error {exc}") from exc

            # update backendstats (optional for backends, but this one has so many information that are easy to display)
            # exposure time needs math on a possibly None value, do it here separate because None/1000 raises an exception.
            if _metadata:
                exposure_time = _metadata.get("ExposureTime", None)
                exposure_time_ms_raw = exposure_time / 1000 if exposure_time is not None else None
                self._backendstats.exposure_time_ms = self._round_none(exposure_time_ms_raw, 1)
                self._backendstats.lens_position = self._round_none(_metadata.get("LensPosition", None), 2)
                self._backendstats.again = self._round_none(_metadata.get("AnalogueGain", None), 1)
                self._backendstats.dgain = self._round_none(_metadata.get("DigitalGain", None), 1)
                self._backendstats.lux = self._round_none(_metadata.get("Lux", None), 1)
                self._backendstats.colour_temperature = _metadata.get("ColourTemperature", None)
                self._backendstats.sharpness = _metadata.get("FocusFoM", None)
            else:
                logger.warning("no metadata available!")

            self._frame_tick()

        logger.info("_generate_images_fun left")
