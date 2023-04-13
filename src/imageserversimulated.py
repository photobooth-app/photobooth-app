"""
Simulated backend for testing.
"""
import platform
import time
import logging
from io import BytesIO
from multiprocessing import Process, shared_memory, Condition, Lock, Event
from PIL import Image, ImageDraw, ImageFont
import psutil
from pymitter import EventEmitter
from src.imageserverabstract import (
    ImageServerAbstract,
    compile_buffer,
    decompile_buffer,
    BackendStats,
)
from src.configsettings import settings

logger = logging.getLogger(__name__)


class ImageServerSimulated(ImageServerAbstract):
    """simulated backend to test photobooth"""

    def __init__(self, ee: EventEmitter, enableStream):
        super().__init__(ee, enableStream)

        # public props (defined in abstract class also)
        self.metadata = {}

        # private props
        self._img_buffer_shm: shared_memory.SharedMemory
        self._condition_img_buffer_ready = Condition()
        self._img_buffer_lock = Lock()
        self._event_proc_shutdown: Event = Event()

        self._p: Process

    def start(self):
        """To start the image backend"""
        # ensure shutdown event is cleared (needed for restart during testing)
        self._event_proc_shutdown.clear()

        self._img_buffer_shm = shared_memory.SharedMemory(
            create=True,
            size=settings._shared_memory_buffer_size,  # pylint: disable=W0212
        )

        self._p = Process(
            target=img_aquisition,
            name="ImageServerSimulatedAquisitionProcess",
            args=(
                self._img_buffer_shm.name,
                self._condition_img_buffer_ready,
                self._img_buffer_lock,
                self._event_proc_shutdown,
            ),
            daemon=True,
        )
        self._p.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        """To stop the image backend"""
        # signal process to shutdown properly
        self._event_proc_shutdown.set()

        # wait until shutdown finished
        self._p.join(timeout=1)
        self._p.close()

        self._img_buffer_shm.close()
        self._img_buffer_shm.unlink()

        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        self._evtbus.emit("frameserver/onCapture")

        # get img off the producing queue
        with self._condition_img_buffer_ready:
            if not self._condition_img_buffer_ready.wait(timeout=4):
                raise TimeoutError("timeout receiving frames")

            with self._img_buffer_lock:
                img = decompile_buffer(self._img_buffer_shm)

        # virtual delay for camera to create picture
        time.sleep(0.1)

        self._evtbus.emit("frameserver/onCaptureFinished")

        # return to previewmode
        self._on_preview_mode()

        return img

    def stats(self) -> BackendStats:
        return BackendStats(
            backend_name=__name__,
        )

    #
    # INTERNAL FUNCTIONS
    #

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        if self._event_proc_shutdown.is_set():
            raise RuntimeError("shutdown already in progress, abort early")

        with self._condition_img_buffer_ready:
            if not self._condition_img_buffer_ready.wait(timeout=4):
                raise TimeoutError("timeout receiving frames")

        with self._img_buffer_lock:
            img = decompile_buffer(self._img_buffer_shm)

        return img

    def _wait_for_lores_frame(self):
        """autofocus not supported by this backend"""
        raise NotImplementedError()

    def _on_capture_mode(self):
        logger.debug("change to capture mode - means doing nothing in simulate")

    def _on_preview_mode(self):
        logger.debug("change to preview mode - means doing nothing in simulate")

    #
    # INTERNAL IMAGE GENERATOR
    #


def img_aquisition(
    shm_buffer_name,
    _condition_img_buffer_ready: Condition,
    _img_buffer_lock: Lock,
    _event_proc_shutdown: Event,
):
    """function started in separate process to deliver images"""
    target_fps = 15
    last_time = time.time_ns()
    shm = shared_memory.SharedMemory(shm_buffer_name)

    while not _event_proc_shutdown.is_set():
        now_time = time.time_ns()
        if (now_time - last_time) / 1000**3 <= (1 / target_fps):
            # limit max framerate to every ~2ms
            time.sleep(2 / 1000.0)
            continue

        fps = round(1 / (now_time - last_time) * 1000**3, 1)
        last_time = now_time

        # create PIL image
        img = Image.new(mode="RGB", size=(640, 480), color="green")

        # add text
        img_draw = ImageDraw.Draw(img)
        font_large = ImageFont.truetype(
            font="./vendor/fonts/Roboto/Roboto-Bold.ttf", size=30
        )
        font_small = ImageFont.truetype(
            font="./vendor/fonts/Roboto/Roboto-Bold.ttf", size=15
        )
        img_draw.text(
            (100, 100), "simulated image backend", fill=(200, 200, 200), font=font_large
        )
        img_draw.text(
            (100, 140), f"img time: {now_time}", fill=(200, 200, 200), font=font_large
        )
        img_draw.text(
            (100, 180), f"framerate: {fps}", fill=(200, 200, 200), font=font_large
        )
        img_draw.text(
            (100, 220),
            (
                f"cpu: 1/5/15min "
                f"{[round(x / psutil.cpu_count() * 100,1) for x in psutil.getloadavg()]}%"
            ),
            fill=(200, 200, 200),
            font=font_large,
        )
        img_draw.text(
            (100, 260),
            "you see this, so installation was successful :)",
            fill=(200, 200, 200),
            font=font_small,
        )
        img_draw.text(
            (100, 280),
            f"goto http://{platform.node()}:{settings.common.webserver_port} to setup",
            fill=(200, 200, 200),
            font=font_small,
        )
        img_draw.text(
            (100, 300),
            "to use a camera instead this simulated backend",
            fill=(200, 200, 200),
            font=font_small,
        )

        # create jpeg
        jpeg_buffer = BytesIO()
        img.save(jpeg_buffer, format="jpeg", quality=90)

        # put jpeg on queue until full. If full this function blocks until queue empty
        with _img_buffer_lock:
            compile_buffer(shm, jpeg_buffer.getvalue())

        with _condition_img_buffer_ready:
            # wait to be notified
            _condition_img_buffer_ready.notify_all()
