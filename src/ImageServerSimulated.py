import platform
import socket
import psutil
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import time
import logging
from pymitter import EventEmitter
import ImageServerAbstract
from ConfigSettings import settings
from multiprocessing import Process, Event, shared_memory, Condition, Lock

logger = logging.getLogger(__name__)


class ImageServerSimulated(ImageServerAbstract.ImageServerAbstract):
    def __init__(self, ee: EventEmitter, enableStream):
        super().__init__(ee, enableStream)

        # public props (defined in abstract class also)
        self.exif_make = "Photobooth FrameServer Simulate"
        self.exif_model = "Custom"
        self.metadata = {}

        # private props
        self._img_buffer_shm = shared_memory.SharedMemory(
            create=True, size=settings._shared_memory_buffer_size)
        self._condition_img_buffer_ready = Condition()
        self._img_buffer_lock = Lock()

        self._p = Process(target=img_aquisition, name="ImageServerSimulatedAquisitionProcess", args=(
            self._img_buffer_shm.name, self._condition_img_buffer_ready, self._img_buffer_lock), daemon=True)

    def start(self):
        """To start the FrameServer"""

        self._p.start()
        logger.debug(f"{self.__module__} started")

    def stop(self):
        """To stop the FrameServer"""
        self._img_buffer_shm.close()
        self._img_buffer_shm.unlink()
        self._p.terminate()
        self._p.join(1)
        self._p.close()

        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        self._ee.emit("frameserver/onCapture")

        # get img off the producing queue
        with self._condition_img_buffer_ready:
            if not self._condition_img_buffer_ready.wait(2):
                raise IOError("timeout receiving frames")

            with self._img_buffer_lock:
                img = ImageServerAbstract.decompileBuffer(
                    self._img_buffer_shm)

        # virtual delay for camera to create picture
        time.sleep(0.1)

        self._ee.emit("frameserver/onCaptureFinished")

        # return to previewmode
        self._onPreviewMode()

        return img

    def gen_stream(self):
        lastTime = time.time_ns()
        while True:
            nowTime = time.time_ns()
            if ((nowTime-lastTime)/1000**3 >= (1/settings.common.LIVEPREVIEW_FRAMERATE)):
                lastTime = nowTime

                buffer = self._wait_for_lores_image()

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer + b'\r\n\r\n')

    def trigger_hq_capture(self):
        self._onCaptureMode()

    """
    INTERNAL FUNCTIONS
    """

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""

        with self._condition_img_buffer_ready:
            if not self._condition_img_buffer_ready.wait(2):
                raise IOError("timeout receiving frames")

        with self._img_buffer_lock:

            img = ImageServerAbstract.decompileBuffer(
                self._img_buffer_shm)

        return img

    def _wait_for_lores_frame(self):
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


def img_aquisition(shm_buffer_name,
                   _condition_img_buffer_ready: Condition,
                   _img_buffer_lock: Lock):

    target_fps = 15
    lastTime = time.time_ns()
    shm = shared_memory.SharedMemory(shm_buffer_name)

    while True:

        nowTime = time.time_ns()
        if ((nowTime-lastTime)/1000**3 <= (1/target_fps)):
            # limit max framerate to every ~2ms
            time.sleep(2/1000.)
            continue

        fps = round(1/(nowTime-lastTime)*1000**3, 1)
        lastTime = nowTime

        # create PIL image
        img = Image.new(
            mode="RGB",
            size=(640,
                  480),
            color="green")

        # add text
        I1 = ImageDraw.Draw(img)
        fontDefault = ImageFont.truetype(
            font="./vendor/fonts/Roboto/Roboto-Bold.ttf",
            size=30)
        fontSmall = ImageFont.truetype(
            font="./vendor/fonts/Roboto/Roboto-Bold.ttf",
            size=15)
        I1.text((100, 100),
                f"simulated image backend",
                fill=(200, 200, 200),
                font=fontDefault)
        I1.text((100, 140),
                f"img time: {nowTime}",
                fill=(200, 200, 200),
                font=fontDefault)
        I1.text((100, 180),
                f"framerate: {fps}",
                fill=(200, 200, 200),
                font=fontDefault)
        I1.text((100, 220),
                f"cpu: 1/5/15min {[round(x / psutil.cpu_count() * 100,1) for x in psutil.getloadavg()]}%",
                fill=(200, 200, 200),
                font=fontDefault)
        I1.text((100, 260),
                f"you see this, so installation was successful :)",
                fill=(200, 200, 200),
                font=fontSmall)
        I1.text((100, 280),
                f"visit http://{platform.node()}:{settings.common.webserver_port} and configure backend",
                fill=(200, 200, 200),
                font=fontSmall)
        I1.text((100, 300),
                f"to use a camera instead this simulated backend",
                fill=(200, 200, 200),
                font=fontSmall)

        # create jpeg
        jpeg_buffer = BytesIO()
        img.save(jpeg_buffer, format="jpeg", quality=90)

        # put jpeg on queue until full. If full this function blocks until queue empty
        with _img_buffer_lock:
            ImageServerAbstract.compileBuffer(shm, jpeg_buffer.getvalue())

        with _condition_img_buffer_ready:
            # wait to be notified
            _condition_img_buffer_ready.notify_all()
