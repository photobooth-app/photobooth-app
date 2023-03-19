"""
Picam2 backend implementation

"""
from threading import Condition
import time
import dataclasses
import logging
import numpy
from pymitter import EventEmitter

try:
    from libcamera import Transform
    from picamera2 import Picamera2
except ImportError as import_exc:
    raise OSError("smbus not supported on windows platform") from import_exc
from turbojpeg import TurboJPEG, TJPF_RGB, TJSAMP_422
from cv2 import cvtColor, COLOR_YUV420p2RGB
from src.configsettings import settings
from src.stoppablethread import StoppableThread
from src.imageserverpicam2_addoncustomautofocus import (
    ImageServerPicam2AddonCustomAutofocus,
)
from src.imageserverpicam2_addonlibcamautofocus import (
    ImageServerPicam2AddonLibcamAutofocus,
)
from src.imageserverabstract import ImageServerAbstract, BackendStats


logger = logging.getLogger(__name__)
turbojpeg = TurboJPEG()


class ImageServerPicam2(ImageServerAbstract):
    """
    The backend implementation using picam2
    """

    @dataclasses.dataclass
    class PicamDataArray:
        """
        bundle data array and it's condition.
        1) save some instance attributes and
        2) bundle as it makes sense
        """

        array: numpy.ndarray = None
        condition: Condition = None

    def __init__(self, evtbus: EventEmitter, enableStream):
        super().__init__(evtbus, enableStream)
        # public props (defined in abstract class also)
        self.exif_make = "Photobooth Picamera2 Integration"
        self.exif_model = "Custom"
        self.metadata = {}

        # private props
        """A simple class that can serve up frames from one of the Picamera2's configured
        streams to multiple other threads.
        Pass in the Picamera2 object and the name of the stream for which you want
        to serve up frames."""
        self._picam2 = Picamera2()

        self._evtbus = evtbus
        if settings.focuser.ENABLED:
            # custom autofocus (has ROI, ... might be removed in future if
            # libcam support for autofocus is well)
            self._addon_autofocus = ImageServerPicam2AddonCustomAutofocus(self, evtbus)
        else:
            self._addon_autofocus = ImageServerPicam2AddonLibcamAutofocus(self, evtbus)

        self._hires_data: ImageServerPicam2.PicamDataArray = (
            ImageServerPicam2.PicamDataArray(array=None, condition=Condition())
        )

        self._lores_data: ImageServerPicam2.PicamDataArray = (
            ImageServerPicam2.PicamDataArray(array=None, condition=Condition())
        )

        self._trigger_hq_capture = False
        self._currentmode = None
        self._lastmode = None
        self._count = 0
        self._fps = 0

        # worker threads
        self._generate_images_thread = StoppableThread(
            name="_generateImagesThread", target=self._generate_images_fun, daemon=True
        )
        self._stats_thread = StoppableThread(
            name="_statsThread", target=self._stats_fun, daemon=True
        )

        # config HQ mode (used for picture capture and live preview on countdown)
        self._capture_config = self._picam2.create_still_configuration(
            {
                "size": (
                    settings.common.CAPTURE_CAM_RESOLUTION_WIDTH,
                    settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT,
                )
            },
            {
                "size": (
                    settings.common.LIVEVIEW_RESOLUTION_WIDTH,
                    settings.common.LIVEVIEW_RESOLUTION_HEIGHT,
                )
            },
            encode="lores",
            buffer_count=2,
            display="lores",
            transform=Transform(
                hflip=settings.common.CAMERA_TRANSFORM_HFLIP,
                vflip=settings.common.CAMERA_TRANSFORM_VFLIP,
            ),
        )

        # config preview mode (used for permanent live view)
        self._preview_config = self._picam2.create_video_configuration(
            {
                "size": (
                    settings.common.PREVIEW_CAM_RESOLUTION_WIDTH,
                    settings.common.PREVIEW_CAM_RESOLUTION_HEIGHT,
                )
            },
            {
                "size": (
                    settings.common.LIVEVIEW_RESOLUTION_WIDTH,
                    settings.common.LIVEVIEW_RESOLUTION_HEIGHT,
                )
            },
            encode="lores",
            buffer_count=2,
            display="lores",
            transform=Transform(
                hflip=settings.common.CAMERA_TRANSFORM_HFLIP,
                vflip=settings.common.CAMERA_TRANSFORM_VFLIP,
            ),
        )

        # activate preview mode on init
        self._on_preview_mode()
        self._picam2.configure(self._currentmode)

        logger.info(f"camera_config: {self._picam2.camera_config}")
        logger.info(f"camera_controls: {self._picam2.camera_controls}")
        logger.info(f"controls: {self._picam2.controls}")

        self.set_ae_exposure(settings.backends.picam2_AE_EXPOSURE_MODE)

    def start(self):
        """To start the FrameServer, you will also need to start the Picamera2 object."""
        # start camera
        self._picam2.start()

        self._generate_images_thread.start()
        self._stats_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        """To stop the FrameServer, first stop any client threads (that might be
        blocked in wait_for_frame), then call this stop method. Don't stop the
        Picamera2 object until the FrameServer has been stopped."""

        self._generate_images_thread.stop()
        self._stats_thread.stop()

        self._generate_images_thread.join(1)
        self._stats_thread.join(1)

        self._picam2.stop()

        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        with self._hires_data.condition:
            while True:
                if not self._hires_data.condition.wait(2):
                    raise IOError("timeout receiving frames")

                buffer = self._get_jpeg_by_hires_frame(
                    frame=self._hires_data.array,
                    quality=settings.common.HIRES_STILL_QUALITY,
                )
                return buffer

    def trigger_hq_capture(self):
        self._trigger_hq_capture = True

    def stats(self) -> BackendStats:
        # exposure time needs math on a possibly None value, do it here separate
        # because None/1000 raises an exception.
        exposure_time = self.metadata.get("ExposureTime", None)
        exposure_time_ms_raw = (
            exposure_time / 1000 if exposure_time is not None else None
        )
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
        with self._lores_data.condition:
            while True:
                if not self._lores_data.condition.wait(2):
                    raise IOError("timeout receiving frames")
                buffer = self._get_jpeg_by_lores_frame(
                    frame=self._lores_data.array,
                    quality=settings.common.LIVEPREVIEW_QUALITY,
                )
                return buffer

    def _wait_for_lores_frame(self):
        """for other threads to receive a lores frame"""
        with self._lores_data.condition:
            while True:
                if not self._lores_data.condition.wait(2):
                    raise IOError("timeout receiving frames")
                return self._lores_data.array

    def _on_capture_mode(self):
        logger.debug("change to capture mode")
        self._lastmode = self._currentmode
        self._currentmode = self._capture_config

    def _on_preview_mode(self):
        logger.debug("change to preview mode")
        self._lastmode = self._currentmode
        self._currentmode = self._preview_config

    def _get_jpeg_by_hires_frame(self, frame, quality):
        jpeg_buffer = turbojpeg.encode(
            frame, quality=quality, pixel_format=TJPF_RGB, jpeg_subsample=TJSAMP_422
        )

        return jpeg_buffer

    def _get_jpeg_by_lores_frame(self, frame, quality):
        jpeg_buffer = turbojpeg.encode(frame, quality=quality)
        return jpeg_buffer

    def set_ae_exposure(self, newmode):
        """_summary_

        Args:
            newmode (_type_): _description_
        """
        logger.info(f"set_ae_exposure, try to set to {newmode}")
        try:
            self._picam2.set_controls({"AeExposureMode": newmode})
        except RuntimeError as exc:
            # catch runtimeerror and no reraise, can fail and being logged but continue.
            logger.error(f"set_ae_exposure failed! Mode {newmode} not available {exc}")

        logger.info(
            f"current picam2.controls.get_libcamera_controls():"
            f"{self._picam2.controls.get_libcamera_controls()}"
        )

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
            if (
                self._trigger_hq_capture is True
                and self._currentmode != self._capture_config
            ):
                # ensure cam is in capture quality mode even if there was no countdown
                # triggered beforehand usually there is a countdown, but this is to be safe
                logger.warning(
                    "force switchmode to capture config right before taking picture"
                )
                self._on_capture_mode()

            if (not self._currentmode == self._lastmode) and self._lastmode is not None:
                logger.info("switch_mode invoked")
                self._picam2.switch_mode(self._currentmode)
                self._lastmode = self._currentmode

            if not self._trigger_hq_capture:
                (orig_array,), self.metadata = self._picam2.capture_arrays(["lores"])

                # convert colors to rgb because lores-stream is always YUV420 that
                # is not used in application usually.
                array = cvtColor(orig_array, COLOR_YUV420p2RGB)

                with self._lores_data.condition:
                    self._lores_data.array = array
                    self._lores_data.condition.notify_all()
            else:
                # only capture one pic and return to lores streaming afterwards
                self._trigger_hq_capture = False

                self._evtbus.emit("frameserver/onCapture")

                # capture hq picture
                (array,), self.metadata = self._picam2.capture_arrays(["main"])
                logger.info(self.metadata)

                self._evtbus.emit("frameserver/onCaptureFinished")

                with self._hires_data.condition:
                    self._hires_data.array = array

                    self._hires_data.condition.notify_all()

                # switch back to preview mode
                self._on_preview_mode()

            self._count += 1
