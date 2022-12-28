import numpy as np
from PIL import Image, ImageDraw
from io import BytesIO
from threading import Condition
import time
import logging
from pymitter import EventEmitter
import lib.ImageServerAbstract
import lib.StoppableThread
logger = logging.getLogger(__name__)


class ImageServerSimulated(lib.ImageServerAbstract.ImageServerAbstract):
    def __init__(self, ee):
        # public props (defined in abstract class also)
        self.exif_make = "Photobooth FrameServer Simulate"
        self.exif_model = "Custom"
        self.metadata = {}

        # private props
        self._hq_img_buffer = None
        self._lores_img_buffer = None
        self._hq_condition = Condition()
        self._lores_condition = Condition()
        self._trigger_hq_capture = False

        self.CYCLE_WAIT = 33  # generate image every XX ms

        super().__init__(ee)

        self._generateImagesThread = lib.StoppableThread.StoppableThread(name="_generateImagesThread",
                                                                         target=self._GenerateImagesFun, daemon=True)

    def start(self):
        """To start the FrameServer"""
        self._generateImagesThread.start()

    def stop(self):
        """To stop the FrameServer"""
        self._generateImagesThread.stop()

    def wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        with self._lores_condition:
            while True:
                self._lores_condition.wait()
                return self._lores_img_buffer.getvalue()

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        with self._hq_condition:
            while True:
                self._hq_condition.wait()
                return self._hq_img_buffer.getvalue()

    def gen_stream(self):
        while not self._generateImagesThread.stopped():
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + self.wait_for_lores_image() + b'\r\n\r\n')

    def trigger_hq_capture(self):
        self._trigger_hq_capture = True
        self._onCaptureMode()

    @property
    def fps(self):
        return round((1/self.CYCLE_WAIT)*1000, 1)

    """
    INTERNAL FUNCTIONS
    """

    def _onCaptureMode(self):
        logger.debug(
            "change to capture mode - means doing nothing in simulate")
        pass

    def _onPreviewMode(self):
        logger.debug(
            "change to preview mode - means doing nothing in simulate")
        pass

    """
    INTERNAL IMAGE GENERATOR
    """

    def _GenerateImagesFun(self):
        counter = 0
        img_array = None

        while not self._generateImagesThread.stopped():  # repeat until stopped
            counter += 1
            # print(counter)

            # create PIL image
            img = Image.new(mode="RGB", size=(2000, 1200), color="green")
            # add text
            I1 = ImageDraw.Draw(img)
            I1.text((100, 100), "simulated image backend",
                    fill=(200, 200, 200))
            I1.text((100, 150), str(counter), fill=(
                200, 200, 200))
            I1.text((100, 200), str((self.fps)),
                    fill=(200, 200, 200))
            # create jpeg
            jpeg_buffer = BytesIO()
            img.save(jpeg_buffer, format="jpeg", quality=90)

            if not self._trigger_hq_capture:
                _lores_data = jpeg_buffer

                with self._lores_condition:
                    self._lores_img_buffer = _lores_data
                    self._lores_condition.notify_all()
            else:
                logger.debug(
                    "triggered capture")
                # only capture one pic and return to lores streaming afterwards
                self._trigger_hq_capture = False

                self._ee.emit("frameserver/onCapture")

                # virtual delay for camera to create picture
                time.sleep(0.3)

                self._ee.emit("frameserver/onCaptureFinished")

                logger.debug(f"metadata={self.metadata}")

                with self._hq_condition:
                    self._hq_img_buffer = jpeg_buffer
                    self._hq_condition.notify_all()

                # switch back to preview mode
                self._onPreviewMode()

            time.sleep(self.CYCLE_WAIT/1000.)
        return


if __name__ == '__main__':
    # setup for testing.
    logging.basicConfig()
    logger.setLevel("DEBUG")

    framserverSimulate = FrameServerSimulate(EventEmitter())

    while (True):
        time.sleep(2)
        framserverSimulate.trigger_hq_capture()
