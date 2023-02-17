import cv2
import ImageServerAbstract
import logging

import platform
from StoppableThread import StoppableThread
from pymitter import EventEmitter
from threading import Condition
from ConfigSettings import settings
from turbojpeg import TurboJPEG, TJPF_RGB, TJSAMP_422
import json
from threading import Condition


logger = logging.getLogger(__name__)


class ImageServerWebcamCv2(ImageServerAbstract.ImageServerAbstract):
    def __init__(self, ee: EventEmitter, enableStream):
        super().__init__(ee, enableStream)
        # public props (defined in abstract class also)
        self.exif_make = "Photobooth WebcamCv2"
        self.exif_model = "Custom"
        self.metadata = {}

        # private props
        self._video = None
        self._turboJPEG = TurboJPEG()
        self._ee = ee

        self._hq_array = None
        self._lores_array = None
        self._hq_condition = Condition()
        self._lores_condition = Condition()
        self._trigger_hq_capture = False
        self._count = 0
        self._fps = 0

        self.openCamera()

        # worker threads
        self._generateImagesThread = StoppableThread(name="_generateImagesThread",
                                                     target=self._GenerateImagesFun, daemon=True)

        self._onPreviewMode()

    def openCamera(self):
        if platform.system() == "Windows":
            logger.info(
                "force VideoCapture to DSHOW backend on windows (MSMF is buggy with OpenCv and crashes app)")
            self._video = cv2.VideoCapture(
                settings.backends.cv2_device_index, cv2.CAP_DSHOW)
        else:
            self._video = cv2.VideoCapture(
                settings.backends.cv2_device_index)

        if not self._video.isOpened():
            raise IOError(
                f"cannot open camera index {settings.backends.cv2_device_index}")

        if not self._video.read()[0]:
            raise IOError(
                f"cannot read camera index {settings.backends.cv2_device_index}")

        logger.info(f"webcam cv2 using backend {self._video.getBackendName()}")

        # activate preview mode on init
        self._video.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        # self._video.set(cv2.CAP_PROP_FPS, 30.0)
        self._video.set(cv2.CAP_PROP_FRAME_WIDTH,
                        settings.common.CAPTURE_CAM_RESOLUTION_WIDTH)
        self._video.set(cv2.CAP_PROP_FRAME_HEIGHT,
                        settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT)

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

        self._video.release()

        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        with self._hq_condition:
            while True:
                # TODO: timout to make it continue and do not block threads completely
                if not self._hq_condition.wait(5):
                    raise IOError("timeout receiving frames")
                buffer = self._getJpegByHiresFrame(
                    frame=self._hq_array, quality=settings.common.HIRES_STILL_QUALITY)
                return buffer

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

    @property
    def fps(self):
        return round(self._fps, 1)

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
                buffer = self._getJpegByLoresFrame(
                    frame=self._lores_array, quality=settings.common.LIVEPREVIEW_QUALITY)
                return buffer

    def _onCaptureMode(self):
        logger.debug(
            "change to capture mode requested - currently no way for webcam to switch within reasonable time")

    def _onPreviewMode(self):
        logger.debug(
            "change to preview mode requested - currently no way for webcam to switch within reasonable time")

    def _getJpegByHiresFrame(self, frame, quality):
        jpeg_buffer = self._turboJPEG.encode(
            frame, quality=quality)

        return jpeg_buffer

    def _getJpegByLoresFrame(self, frame, quality):
        jpeg_buffer = self._turboJPEG.encode(
            frame, quality=quality)

        return jpeg_buffer

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

            if not self._trigger_hq_capture:
                ret, array = self._video.read()
                # ret=True successful read, otherwise False?
                if not ret:
                    raise IOError("error reading camera frame")

                # apply flip image to stream only:
                if settings.common.CAMERA_TRANSFORM_HFLIP:
                    array = cv2.flip(array, 1)
                if settings.common.CAMERA_TRANSFORM_VFLIP:
                    array = cv2.flip(array, 0)

                with self._lores_condition:
                    self._lores_array = array
                    self._lores_condition.notify_all()
            else:
                # only capture one pic and return to lores streaming afterwards
                self._trigger_hq_capture = False

                self._ee.emit("frameserver/onCapture")

                # capture hq picture
                ret, array = self._video.read()
                if not ret:
                    raise IOError("error reading camera frame")

                # optional denoise?
                array = cv2.fastNlMeansDenoisingColored(
                    array, None, 2, 2, 3, 9)

                logger.debug(self.metadata)

                self._ee.emit("frameserver/onCaptureFinished")

                with self._hq_condition:
                    self._hq_array = array
                    self._hq_condition.notify_all()

                # switch back to preview mode
                self._onPreviewMode()

            self._count += 1
