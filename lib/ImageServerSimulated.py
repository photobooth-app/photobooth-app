import threading
import psutil
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from threading import Condition
import time
import logging
from pymitter import EventEmitter
import ImageServerAbstract
import StoppableThread
from ConfigSettings import settings
logger = logging.getLogger(__name__)


class ImageServerSimulated(ImageServerAbstract.ImageServerAbstract):
    def __init__(self, ee):
        super().__init__(ee)

        # public props (defined in abstract class also)
        self.exif_make = "Photobooth FrameServer Simulate"
        self.exif_model = "Custom"
        self.metadata = {}
        self.providesStream = True

        # private props
        self._hq_img_buffer = None
        self._lores_img_buffer = None
        self._hq_condition = Condition()
        self._lores_condition = Condition()
        self._trigger_hq_capture = False

        self.CYCLE_WAIT = 33  # generate image every XX ms

        self._generateImagesThread = StoppableThread.StoppableThread(name="_generateImagesThread",
                                                                     target=self._GenerateImagesFun, daemon=True)

    def start(self):
        """To start the FrameServer"""
        self._generateImagesThread.start()
        logger.debug(f"{self.__module__} started")

    def stop(self):
        """To stop the FrameServer"""
        self._generateImagesThread.stop()
        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        with self._hq_condition:
            while True:
                if not self._hq_condition.wait(1):
                    raise IOError("timeout receiving frames")
                return self._hq_img_buffer.getvalue()

    def gen_stream(self):
        while not self._generateImagesThread.stopped():
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + self._wait_for_lores_image() + b'\r\n\r\n')

    def trigger_hq_capture(self):
        self._trigger_hq_capture = True
        self._onCaptureMode()

    @property
    def fps(self):
        return round((1/self.CYCLE_WAIT)*1000, 1)

    """
    INTERNAL FUNCTIONS
    """

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        with self._lores_condition:
            while True:
                if not self._lores_condition.wait(1):
                    raise IOError("timeout receiving frames")
                return self._lores_img_buffer.getvalue()

    def _wait_for_autofocus_frame(self):
        """autofocus not supported by this backend"""
        raise NotImplementedError()

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

        while not self._generateImagesThread.stopped():  # repeat until stopped
            counter += 1

            # create PIL image
            img = Image.new(
                mode="RGB",
                size=settings.common.CAPTURE_VIDEO_RESOLUTION,
                color="green")

            # add text
            I1 = ImageDraw.Draw(img)
            font = ImageFont.truetype(
                font="./vendor/fonts/Roboto/Roboto-Bold.ttf",
                size=50)
            I1.text((200, 200),
                    f"simulated image backend",
                    fill=(200, 200, 200),
                    font=font)
            I1.text((200, 250),
                    f"img no counter: {counter}",
                    fill=(200, 200, 200),
                    font=font)
            I1.text((200, 300),
                    f"framerate: {self.fps}",
                    fill=(200, 200, 200),
                    font=font)
            I1.text((200, 350),
                    f"cpu: 1/5/15min {[round(x / psutil.cpu_count() * 100,1) for x in psutil.getloadavg()]}%",
                    fill=(200, 200, 200),
                    font=font)
            I1.text((200, 400),
                    f"active threads #{threading.active_count()}",
                    fill=(200, 200, 200),
                    font=font)

            # create jpeg
            jpeg_buffer = BytesIO()
            img.save(jpeg_buffer, format="jpeg", quality=90)

            if not self._trigger_hq_capture:
                with self._lores_condition:
                    self._lores_img_buffer = jpeg_buffer
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


# Test function for module
def _test():
    # setup for testing.
    from PIL import Image
    import io
    logging.basicConfig()
    logger.setLevel("DEBUG")

    imageServer = ImageServerSimulated(EventEmitter())
    imageServer.start()

    time.sleep(1)

    try:
        with Image.open(io.BytesIO(imageServer._wait_for_lores_image())) as im:
            im.verify()
    except:
        raise AssertionError("backend did not return valid image bytes")

    imageServer.trigger_hq_capture()
    # time.sleep(1) #TODO: race condition?!

    try:
        with Image.open(io.BytesIO(imageServer.wait_for_hq_image())) as im:
            im.verify()
    except:
        raise AssertionError("backend did not return valid image bytes")

    logger.info("testing finished.")


if __name__ == '__main__':
    _test()
