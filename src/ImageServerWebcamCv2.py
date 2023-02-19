import cv2
import ImageServerAbstract
from multiprocessing import Process, Queue, Value
import logging
import platform
from StoppableThread import StoppableThread
from pymitter import EventEmitter
from threading import Condition
from ConfigSettings import settings
from turbojpeg import TurboJPEG, TJPF_RGB, TJSAMP_422
import json
from threading import Condition
import ctypes

logger = logging.getLogger(__name__)


class ImageServerWebcamCv2(ImageServerAbstract.ImageServerAbstract):
    def __init__(self, ee: EventEmitter, enableStream):
        super().__init__(ee, enableStream)
        # public props (defined in abstract class also)
        self.exif_make = "Photobooth WebcamCv2"
        self.exif_model = "Custom"
        self.metadata = {}

        # private props
        self._ee = ee

        self._img_buffer_queue: Queue = Queue(maxsize=5)
        self._hq_img_buffer_queue: Queue = Queue(maxsize=5)
        self._trigger_hq_capture: Value = Value(ctypes.c_bool, False)

        self._p = Process(target=img_aquisition, name="ImageServerWebcamCv2AquisitionProcess", args=(
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
    _turboJPEG = TurboJPEG()

    if platform.system() == "Windows":
        logger.info(
            "force VideoCapture to DSHOW backend on windows (MSMF is buggy with OpenCv and crashes app)")
        _video = cv2.VideoCapture(
            settings.backends.cv2_device_index, cv2.CAP_DSHOW)
    else:
        _video = cv2.VideoCapture(
            settings.backends.cv2_device_index)

    if not _video.isOpened():
        raise IOError(
            f"cannot open camera index {settings.backends.cv2_device_index}")

    if not _video.read()[0]:
        raise IOError(
            f"cannot read camera index {settings.backends.cv2_device_index}")

    logger.info(f"webcam cv2 using backend {_video.getBackendName()}")

    # activate preview mode on init
    _video.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    # self._video.set(cv2.CAP_PROP_FPS, 30.0)
    _video.set(cv2.CAP_PROP_FRAME_WIDTH,
               settings.common.CAPTURE_CAM_RESOLUTION_WIDTH)
    _video.set(cv2.CAP_PROP_FRAME_HEIGHT,
               settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT)

    while True:
        ret, array = _video.read()
        # ret=True successful read, otherwise False?
        if not ret:
            raise IOError("error reading camera frame")

        # apply flip image to stream only:
        if settings.common.CAMERA_TRANSFORM_HFLIP:
            array = cv2.flip(array, 1)
        if settings.common.CAMERA_TRANSFORM_VFLIP:
            array = cv2.flip(array, 0)

        if _trigger_hq_capture.value == True:
            # one time hq still
            array = cv2.fastNlMeansDenoisingColored(
                array, None, 2, 2, 3, 9)
            # convert frame to jpeg buffer
            jpeg_buffer = _turboJPEG.encode(
                array, quality=settings.common.HIRES_STILL_QUALITY)
            # put jpeg on queue until full. If full this function blocks until queue empty
            _hq_img_buffer_queue.put(jpeg_buffer)
            _trigger_hq_capture.value = False
        else:
            # preview livestream
            jpeg_buffer = _turboJPEG.encode(
                array, quality=settings.common.LIVEPREVIEW_QUALITY)
            # put jpeg on queue until full. If full this function blocks until queue empty
            _img_buffer_queue.put(jpeg_buffer)

    # TODO: need to close video actually on exit: self._video.release()
