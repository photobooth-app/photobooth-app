from PIL import ImageDraw
from PIL import ImageFont
from ConfigSettings import settings, ConfigSettingsInternal
from turbojpeg import TurboJPEG, TJPF_RGB, TJSAMP_422
import json
import psutil
import threading
from threading import Condition, Thread
import cv2
import PIL
import time
import logging
import FrameServerAbstract
from pymitter import EventEmitter
from StoppableThread import StoppableThread
logger = logging.getLogger(__name__)


class FrameServerSimulate(FrameServerAbstract.FrameServerAbstract):
    def __init__(self, ee):

        self._hq_array = None
        self._lores_array = None
        self._metadata = None
        self._hq_condition = Condition()
        self._lores_condition = Condition()
        self._trigger_hq_capture = False

        super().__init__(ee)

        self._generateImagesThread = StoppableThread(name="_generateImagesThread",
                                                     target=self._GenerateImagesFun, daemon=True)

        self._generateImagesThread.start()

    def wait_for_lores_frame(self):
        """for other threads to receive a lores frame"""
        with self._lores_condition:
            while True:
                self._lores_condition.wait()
                return self._lores_array

    def wait_for_hq_frame(self):
        """for other threads to receive a hq frame"""
        with self._hq_condition:
            while True:
                self._hq_condition.wait()
                return self._hq_array

    def gen_stream(self):
        while not self._generateImagesThread.stopped():
            frame = self.wait_for_lores_frame()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

    def trigger_hq_capture(self):
        self._trigger_hq_capture = True
        self._onCaptureMode()

    def wait_for_hq_image(self):
        # img.save("result.jpg")
        pass

    def get_metadata(self):
        return {}

    def _onCaptureMode(self):
        logger.debug(
            "change to capture mode - means doing nothing in simulate")
        pass

    def _onPreviewMode(self):
        logger.debug(
            "change to preview mode - means doing nothing in simulate")
        pass

    ####
    def _GenerateImagesFun(self):
        counter = 0

        while not self._generateImagesThread.stopped():  # repeat until stopped
            counter += 1
            # print(counter)

            # create PIL image
            img = PIL.Image.new(mode="RGB", size=(600, 500))

            # add text
            I1 = ImageDraw.Draw(img)
            I1.text((28, 36), str(counter), fill=(255, 0, 0))

            if not self._trigger_hq_capture:
                _lores_data = img

                with self._lores_condition:
                    self._lores_array = _lores_data
                    self._lores_condition.notify_all()
            else:
                logger.debug(
                    "triggered capture")
                # only capture one pic and return to lores streaming afterwards
                self._trigger_hq_capture = False

                self._ee.emit("frameserver/onCapture")

                # capture hq picture
                _hires_data = img
                logger.debug(f"metadata={self._metadata}")

                self._ee.emit("frameserver/onCaptureFinished")

                with self._hq_condition:
                    self._hq_array = _hires_data
                    self._hq_condition.notify_all()

                # switch back to preview mode
                self._onPreviewMode()

            time.sleep(33/1000.)

            # img.show()
        return


if __name__ == '__main__':
    # setup for testing.
    logging.basicConfig()
    logger.setLevel("DEBUG")

    framserverSimulate = FrameServerSimulate(EventEmitter())

    while (True):
        time.sleep(2)
        framserverSimulate.trigger_hq_capture()
