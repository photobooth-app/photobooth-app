import time
import cv2
import ImageServerAbstract
from multiprocessing import Process, Event, shared_memory, Condition, Lock
import logging
import platform
from pymitter import EventEmitter
from ConfigSettings import settings
from turbojpeg import TurboJPEG
import json

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

        self._img_buffer_lores_shm = shared_memory.SharedMemory(
            create=True, size=settings._shared_memory_buffer_size)
        self._img_buffer_hires_shm = shared_memory.SharedMemory(
            create=True, size=settings._shared_memory_buffer_size)
        self._event_hq_capture: Event = Event()
        self._condition_img_buffer_hires_ready = Condition()
        self._condition_img_buffer_lores_ready = Condition()
        self._img_buffer_lores_lock = Lock()
        self._img_buffer_hires_lock = Lock()

        self._p = Process(
            target=img_aquisition,
            name="ImageServerWebcamCv2AquisitionProcess",
            args=(
                self._img_buffer_lores_shm.name,
                self._img_buffer_hires_shm.name,
                self._img_buffer_lores_lock,
                self._img_buffer_hires_lock,
                self._event_hq_capture,
                self._condition_img_buffer_hires_ready,
                self._condition_img_buffer_lores_ready
            ),
            daemon=True)

        self._onPreviewMode()

    def start(self):
        """To start the FrameServer, you will also need to start the Picamera2 object."""
        # start camera
        self._p.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        self._img_buffer_lores_shm.close()
        self._img_buffer_lores_shm.unlink()
        self._img_buffer_hires_shm.close()
        self._img_buffer_hires_shm.unlink()
        self._p.terminate()
        self._p.join(1)
        self._p.close()

        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        self._ee.emit("frameserver/onCapture")

        # get img off the producing queue
        with self._condition_img_buffer_hires_ready:
            self._condition_img_buffer_hires_ready.wait(5)

            with self._img_buffer_hires_lock:
                img = ImageServerAbstract.decompileBuffer(
                    self._img_buffer_hires_shm)

        self._ee.emit("frameserver/onCaptureFinished")

        # return to previewmode
        self._onPreviewMode()

        return img

    def gen_stream(self):
        lastTime = time.time_ns()
        while True:
            buffer = self._wait_for_lores_image()

            nowTime = time.time_ns()
            if ((nowTime-lastTime)/1000**3 >= (1/settings.common.LIVEPREVIEW_FRAMERATE)):
                lastTime = nowTime

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer + b'\r\n\r\n')

    def trigger_hq_capture(self):
        self._event_hq_capture.set()
        self._onCaptureMode()

    """
    INTERNAL FUNCTIONS
    """

    def _wait_for_lores_frame(self):
        """autofocus not supported by this backend"""
        raise NotImplementedError()

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        with self._condition_img_buffer_lores_ready:
            self._condition_img_buffer_lores_ready.wait(5)
            with self._img_buffer_lores_lock:
                img = ImageServerAbstract.decompileBuffer(
                    self._img_buffer_lores_shm)
            return img

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


def img_aquisition(
        shm_buffer_lores_name,
        shm_buffer_hires_name,
        _img_buffer_lores_lock,
        _img_buffer_hires_lock,
        _event_hq_capture: Event,
        _condition_img_buffer_hires_ready: Condition,
        _condition_img_buffer_lores_ready: Condition):

    # init
    _turboJPEG = TurboJPEG()
    shm_lores = shared_memory.SharedMemory(shm_buffer_lores_name)
    shm_hires = shared_memory.SharedMemory(shm_buffer_hires_name)

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
    _video.set(cv2.CAP_PROP_FPS, 30.0)
    _video.set(cv2.CAP_PROP_BUFFERSIZE, 2)  # low number for lowest lag
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

        if _event_hq_capture.is_set():

            _event_hq_capture.clear()

            # one time hq still
            array = cv2.fastNlMeansDenoisingColored(
                array, None, 2, 2, 3, 9)

            # convert frame to jpeg buffer
            jpeg_buffer = _turboJPEG.encode(
                array, quality=settings.common.HIRES_STILL_QUALITY)
            # put jpeg on queue until full. If full this function blocks until queue empty
            with _img_buffer_hires_lock:
                ImageServerAbstract.compileBuffer(shm_hires, jpeg_buffer)

            with _condition_img_buffer_hires_ready:
                # wait to be notified
                _condition_img_buffer_hires_ready.notify_all()
        else:
            # preview livestream
            jpeg_buffer = _turboJPEG.encode(
                array, quality=settings.common.LIVEPREVIEW_QUALITY)
            # put jpeg on queue until full. If full this function blocks until queue empty
            with _img_buffer_lores_lock:
                ImageServerAbstract.compileBuffer(shm_lores, jpeg_buffer)

            with _condition_img_buffer_lores_ready:
                # wait to be notified
                _condition_img_buffer_lores_ready.notify_all()

    # TODO: need to close video actually on exit: self._video.release()
