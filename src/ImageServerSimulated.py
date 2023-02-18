from multiprocessing import Process, Queue, Condition
import threading
import psutil
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import time
import logging
from pymitter import EventEmitter
import ImageServerAbstract
import src.StoppableThread as StoppableThread
from ConfigSettings import settings
logger = logging.getLogger(__name__)


class ImageServerSimulated(ImageServerAbstract.ImageServerAbstract):
    def __init__(self, ee: EventEmitter, enableStream):
        super().__init__(ee, enableStream)

        # public props (defined in abstract class also)
        self.exif_make = "Photobooth FrameServer Simulate"
        self.exif_model = "Custom"
        self.metadata = {}

        # private props
        self._img_buffer_queue: Queue = Queue()

        self._p = Process(target=img_generator, args=(self._img_buffer_queue,))

    def start(self):
        """To start the FrameServer"""

        self._p.start()
        logger.debug(f"{self.__module__} started")

    def stop(self):
        """To stop the FrameServer"""

        self._p.terminate()
        self._p.join()
        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        self._ee.emit("frameserver/onCapture")

        # get img off the producing queue
        img = self._img_buffer_queue.get(timeout=1)

        # virtual delay for camera to create picture
        time.sleep(0.1)

        self._ee.emit("frameserver/onCaptureFinished")

        # return to previewmode
        self._onPreviewMode()

        return img

    def gen_stream(self):
        while True:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + self._wait_for_lores_image() + b'\r\n\r\n')

    def trigger_hq_capture(self):
        self._onCaptureMode()

    """
    INTERNAL FUNCTIONS
    """

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        return self._img_buffer_queue.get(timeout=1)

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


def img_generator(queue):
    counter = 0
    fps = 0
    fps_calc_every = 100
    lastTime = time.time_ns()
    while True:

        counter += 1
        if (counter % 100) == 0:
            nowTime = time.time_ns()
            fps = round(fps_calc_every/(nowTime-lastTime)*1000**3, 1)
            lastTime = nowTime

        # create PIL image
        img = Image.new(
            mode="RGB",
            size=(640,
                  480),
            color="green")

        # add text
        I1 = ImageDraw.Draw(img)
        font = ImageFont.truetype(
            font="./vendor/fonts/Roboto/Roboto-Bold.ttf",
            size=30)
        I1.text((100, 100),
                f"simulated image backend",
                fill=(200, 200, 200),
                font=font)
        I1.text((100, 140),
                f"img no counter: {counter}",
                fill=(200, 200, 200),
                font=font)
        I1.text((100, 180),
                f"framerate: {fps}",
                fill=(200, 200, 200),
                font=font)
        I1.text((100, 220),
                f"cpu: 1/5/15min {[round(x / psutil.cpu_count() * 100,1) for x in psutil.getloadavg()]}%",
                fill=(200, 200, 200),
                font=font)
        I1.text((100, 260),
                f"active threads #{threading.active_count()}",
                fill=(200, 200, 200),
                font=font)

        # create jpeg
        jpeg_buffer = BytesIO()
        img.save(jpeg_buffer, format="jpeg", quality=90)

        queue.put(jpeg_buffer.getvalue())

        time.sleep(33/1000.)
