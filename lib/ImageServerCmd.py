import os
from io import BytesIO
from threading import Condition
import time
import logging
from pymitter import EventEmitter
import lib.ImageServerAbstract
import lib.StoppableThread
from .ConfigSettings import settings
logger = logging.getLogger(__name__)


class ImageServerCmd(lib.ImageServerAbstract.ImageServerAbstract):
    def __init__(self, ee):
        super().__init__(ee)

        # public props (defined in abstract class also)
        self.exif_make = "Photobooth FrameServer Simulate"
        self.exif_model = "Custom"
        self.metadata = {}

        # private props
        self._hq_img_buffer = None
        self._hq_condition = Condition()
        self._trigger_hq_capture = False

        self._generateImagesThread = lib.StoppableThread.StoppableThread(name="_generateImagesThread",
                                                                         target=self._GenerateImagesFun, daemon=True)

    def start(self):
        """To start the FrameServer"""
        self._onPreviewMode()

    def stop(self):
        """To stop the FrameServer"""
        pass

    def wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        raise NotImplementedError()

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        with self._hq_condition:
            while True:
                self._hq_condition.wait()
                return self._hq_img_buffer.getvalue()

    def wait_for_lores_frame(self):
        raise NotImplementedError()

    def wait_for_hq_frame(self):
        raise NotImplementedError()

    def gen_stream(self):
        raise NotImplementedError()

    def trigger_hq_capture(self):
        self._onCaptureMode()
        self._trigger_hq_capture = True

    @property
    def fps(self):
        return round((1/self.CYCLE_WAIT)*1000, 1)

    """
    INTERNAL FUNCTIONS
    """

    def _onCaptureMode(self):
        logger.debug(
            "change to capture mode - means disable liveview (if necessary) and prepare to capture HQ pic")
        os.system("")  # execute command

    def _onPreviewMode(self):
        logger.debug(
            "change to preview mode - means enable liveview (if necessary)")
        os.system("")  # execute command

    """
    INTERNAL IMAGE GENERATOR
    """

    def _GenerateImagesFun(self):
        counter = 0

        while not self._generateImagesThread.stopped():  # repeat until stopped
            counter += 1

            if self._trigger_hq_capture:
                # only capture one pic and return to lores streaming afterwards
                self._trigger_hq_capture = False

                logger.debug(
                    "triggered capture")

                self._ee.emit("frameserver/onCapture")

                # virtual delay for camera to create picture
                # capture request, afterwards read file to buffer
                os.system("")
                jpeg_buffer = BytesIO()  # dummy

                self._ee.emit("frameserver/onCaptureFinished")

                # TODO: get metadata

                with self._hq_condition:
                    self._hq_img_buffer = jpeg_buffer
                    self._hq_condition.notify_all()

                # switch back to preview mode
                self._onPreviewMode()

            # wait for trigger...
            time.sleep(0.05)
        return


if __name__ == '__main__':
    # setup for testing.
    logging.basicConfig()
    logger.setLevel("DEBUG")

    framserverSimulate = ImageServerCmd(EventEmitter())

    while (True):
        time.sleep(2)
        framserverSimulate.trigger_hq_capture()
