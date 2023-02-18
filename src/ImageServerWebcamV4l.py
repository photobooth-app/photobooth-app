import ImageServerAbstract
import logging
import platform
if platform.system() == "Windows":
    raise OSError("backend v4l2py not supported on windows platform")
from v4l2py import Device
import platform
from StoppableThread import StoppableThread
from pymitter import EventEmitter
from threading import Condition
from ConfigSettings import settings
import json
from threading import Condition


logger = logging.getLogger(__name__)


class ImageServerWebcamV4l(ImageServerAbstract.ImageServerAbstract):
    def __init__(self, ee: EventEmitter, enableStream):
        super().__init__(ee, enableStream)
        # public props (defined in abstract class also)
        self.exif_make = "Photobooth WebcamV4l"
        self.exif_model = "Custom"
        self.metadata = {}

        # private props
        self._ee = ee

        self._hq_buffer = None
        self._lores_buffer = None
        self._hq_condition = Condition()
        self._lores_condition = Condition()
        self._trigger_hq_capture = False
        self._count = 0
        self._fps = 0

        if platform.system() == "Windows":
            raise OSError("backend v4l not supported on windows platform")

        # worker threads
        self._generateImagesThread = StoppableThread(name="_generateImagesThread",
                                                     target=self._GenerateImagesFun, daemon=True)

        self._onPreviewMode()

    def start(self):
        """To start the FrameServer, you will also need to start the Picamera2 object."""
        # start camera

        self._generateImagesThread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        """To stop the FrameServer, first stop any client threads (that might be
        blocked in wait_for_frame), then call this stop method. Don't stop the
        Picamera2 object until the FrameServer has been stopped."""

        self._generateImagesThread.stop()

        self._generateImagesThread.join(1)

        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        with self._hq_condition:
            while True:
                # TODO: timout to make it continue and do not block threads completely
                if not self._hq_condition.wait(5):
                    raise IOError("timeout receiving frames")

                return self._hq_buffer

    def gen_stream(self):
        skip_counter = settings.common.PREVIEW_PREVIEW_FRAMERATE_DIVIDER

        while not self._generateImagesThread.stopped():
            buffer = self._wait_for_lores_image()

            if (skip_counter <= 1):
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer + b'\r\n\r\n')
                skip_counter = settings.common.PREVIEW_PREVIEW_FRAMERATE_DIVIDER
            else:
                skip_counter -= 1

    def trigger_hq_capture(self):
        self._trigger_hq_capture = True

    """
    INTERNAL FUNCTIONS
    """

    def _wait_for_autofocus_frame(self):
        """autofocus not supported by this backend"""
        raise NotImplementedError()

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        with self._lores_condition:
            while True:
                # TODO: timout to make it continue and do not block threads completely
                if not self._lores_condition.wait(5):
                    raise IOError("timeout receiving frames")

                return self._lores_buffer

    def _onCaptureMode(self):
        logger.debug(
            "change to capture mode requested - currently no way for webcam to switch within reasonable time")

    def _onPreviewMode(self):
        logger.debug(
            "change to preview mode requested - currently no way for webcam to switch within reasonable time")

    def _publishSSEInitial(self):
        self._publishSSE_metadata()

    def _publishSSE_metadata(self):
        self._ee.emit("publishSSE", sse_event="frameserver/metadata",
                      sse_data=json.dumps(self.metadata))

    """
    INTERNAL IMAGE GENERATOR
    """

    def _GenerateImagesFun(self):

        while not self._generateImagesThread.stopped():  # repeat until stopped
            if self._trigger_hq_capture == True:
                # ensure cam is in capture quality mode even if there was no countdown triggered beforehand
                # usually there is a countdown, but this is to be safe
                logger.warning(
                    f"force switchmode to capture config right before taking picture (no countdown?!)")
                self._onCaptureMode()

            with Device.from_id(settings.backends.v4l_device_index) as cam:
                logger.info(
                    f"webcam devices index {settings.backends.v4l_device_index} opened")
                try:
                    cam.video_capture.set_format(
                        settings.common.CAPTURE_CAM_RESOLUTION_WIDTH, settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT, 'MJPG')
                except Exception as e:
                    logger.exception(e)

                for frame in cam:

                    if not self._trigger_hq_capture:

                        with self._lores_condition:
                            self._lores_buffer = frame
                            self._lores_condition.notify_all()
                    else:
                        # only capture one pic and return to lores streaming afterwards
                        self._trigger_hq_capture = False

                        self._ee.emit("frameserver/onCapture")

                        # capture hq picture

                        with self._hq_condition:
                            self._hq_buffer = frame
                            self._hq_condition.notify_all()

                        self._ee.emit("frameserver/onCaptureFinished")

                        # switch back to preview mode
                        self._onPreviewMode()

                    self._count += 1
