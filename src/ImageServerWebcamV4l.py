import ImageServerAbstract
import logging
from multiprocessing import Process, Queue, Value
import platform
if platform.system() == "Windows":
    raise OSError("backend v4l2py not supported on windows platform")
from v4l2py import Device
import platform
from pymitter import EventEmitter
from ConfigSettings import settings
import json
import ctypes

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

        self._img_buffer_queue: Queue = Queue(maxsize=5)
        self._hq_img_buffer_queue: Queue = Queue(maxsize=5)
        self._trigger_hq_capture: Value = Value(ctypes.c_bool, False)

        self._p = Process(target=img_aquisition, name="ImageServerWebcamV4lAquisitionProcess", args=(
            self._img_buffer_queue, self._hq_img_buffer_queue, self._trigger_hq_capture), daemon=True)

        self._onPreviewMode()

    def start(self):
        """To start the FrameServer, you will also need to start the Picamera2 object."""
        # start camera

        self._p.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        """To stop the FrameServer, first stop any client threads (that might be
        blocked in wait_for_frame), then call this stop method. Don't stop the
        Picamera2 object until the FrameServer has been stopped."""

        self._p.terminate()
        self._p.join(1)
        self._p.close()

        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        self._ee.emit("frameserver/onCapture")

        # get img off the producing queue
        img = self._hq_img_buffer_queue.get(timeout=5)

        self._ee.emit("frameserver/onCaptureFinished")

        # return to previewmode
        self._onPreviewMode()

        return img

    def gen_stream(self):
        skip_counter = settings.common.PREVIEW_PREVIEW_FRAMERATE_DIVIDER

        while True:
            buffer = self._wait_for_lores_image()

            if (skip_counter <= 1):
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer + b'\r\n\r\n')
                skip_counter = settings.common.PREVIEW_PREVIEW_FRAMERATE_DIVIDER
            else:
                skip_counter -= 1

    def trigger_hq_capture(self):
        self._trigger_hq_capture.value = True
        self._onCaptureMode()

    """
    INTERNAL FUNCTIONS
    """

    def _wait_for_lores_frame(self):
        """autofocus not supported by this backend"""
        raise NotImplementedError()

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        return self._img_buffer_queue.get(timeout=5)

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


def img_aquisition(_img_buffer_queue, _hq_img_buffer_queue, _trigger_hq_capture):

    # init

    while True:
        with Device.from_id(settings.backends.v4l_device_index) as cam:
            logger.info(
                f"webcam devices index {settings.backends.v4l_device_index} opened")
            try:
                cam.video_capture.set_format(
                    settings.common.CAPTURE_CAM_RESOLUTION_WIDTH, settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT, 'MJPG')
            except Exception as e:
                logger.exception(e)

            for jpeg_buffer in cam:
                if _trigger_hq_capture.value == True:
                    # only capture one pic and return to lores streaming afterwards
                    _trigger_hq_capture.value = False

                    # capture hq picture
                    _hq_img_buffer_queue.put(jpeg_buffer)

                else:
                    # put jpeg on queue until full. If full this function blocks until queue empty
                    _img_buffer_queue.put(jpeg_buffer)
