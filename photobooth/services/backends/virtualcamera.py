"""
Virtual Camera backend for testing.
"""

import glob
import logging
import random
import time
from datetime import datetime
from io import BytesIO
from multiprocessing import Condition, Event, Lock, Process, shared_memory
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..config import appconfig
from .abstractbackend import AbstractBackend, compile_buffer, decompile_buffer

SHARED_MEMORY_BUFFER_BYTES = 1 * 1024**2
FPS_TARGET = 15

logger = logging.getLogger(__name__)


class VirtualCameraBackend(AbstractBackend):
    """Virtual camera backend to test photobooth"""

    def __init__(self):
        super().__init__()
        self._failing_wait_for_lores_image_is_error = True  # missing lores images is automatically considered as error

        self._img_buffer_shm: shared_memory.SharedMemory = None
        self._condition_img_buffer_ready = Condition()
        self._img_buffer_lock = Lock()
        self._event_proc_shutdown: Event = Event()

        self._virtualcamera_process: Process = None

    def _device_start(self):
        """To start the image backend"""
        # ensure shutdown event is cleared (needed for restart during testing)

        self._event_proc_shutdown.clear()

        self._img_buffer_shm = shared_memory.SharedMemory(
            create=True,
            size=SHARED_MEMORY_BUFFER_BYTES,
        )

        self._virtualcamera_process = Process(
            target=img_aquisition,
            name="VirtualCameraAquisitionProcess",
            args=(
                self._img_buffer_shm.name,
                self._condition_img_buffer_ready,
                self._img_buffer_lock,
                self._event_proc_shutdown,
                appconfig.uisettings.livestream_mirror_effect,
                FPS_TARGET,
            ),
            daemon=True,
        )
        # start process
        self._virtualcamera_process.start()

        # wait until threads are up and deliver images actually. raises exceptions if fails after several retries
        self._block_until_delivers_lores_images()

        logger.debug(f"{self.__module__} started")

    def _device_stop(self):
        # signal process to shutdown properly
        self._event_proc_shutdown.set()

        # wait until shutdown finished
        if self._virtualcamera_process:
            # https://stackoverflow.com/a/58866932
            self._virtualcamera_process.join()
            self._virtualcamera_process.close()  # close to allow garbage collection

        if self._img_buffer_shm:
            self._img_buffer_shm.close()
            self._img_buffer_shm.unlink()

        logger.debug(f"{self.__module__} stopped")

    def _device_available(self) -> bool:
        """virtual camera to be available always"""
        return True

    def _wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""

        hq_images = glob.glob(f'{Path(__file__).parent.joinpath("assets", "backend_virtualcamera", "images").resolve()}/*.jpg')
        current_hq_image_index = random.randint(0, len(hq_images) - 1)

        # get img off the producing queue
        logger.info(f"provide {hq_images[current_hq_image_index]} as hq_image")
        img = open(hq_images[current_hq_image_index], "rb").read()

        return img

    #
    # INTERNAL FUNCTIONS
    #

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""

        with self._condition_img_buffer_ready:
            if not self._condition_img_buffer_ready.wait(timeout=0.2):
                raise TimeoutError("timeout receiving frames")

        with self._img_buffer_lock:
            img = decompile_buffer(self._img_buffer_shm)

        return img

    def _on_configure_optimized_for_hq_capture(self):
        pass

    def _on_configure_optimized_for_idle(self):
        pass

    #
    # INTERNAL IMAGE GENERATOR
    #


def img_aquisition(
    shm_buffer_name,
    _condition_img_buffer_ready: Condition,
    _img_buffer_lock: Lock,
    _event_proc_shutdown: Event,
    _mirror: bool,
    _fps_target: int,
):
    """function started in separate process to deliver images"""

    ## Create a logger. INFO: this logger is in separate process and just logs to console.
    # Could be replaced in future by a more sophisticated solution
    logger = logging.getLogger()
    fmt = "%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s) proc%(process)d"
    logging.basicConfig(level=logging.DEBUG, format=fmt)

    logger.info("img_aquisition process started")

    last_time_frame = time.time_ns()
    last_time_newimage = time.time()
    shm = shared_memory.SharedMemory(shm_buffer_name)

    path_font = Path(__file__).parent.joinpath("assets", "backend_virtualcamera", "fonts", "Roboto-Bold.ttf").resolve()

    lores_images = glob.glob(f'{Path(__file__).parent.joinpath("assets", "backend_virtualcamera", "images").resolve()}/*.jpg')
    img_original = [Image.open(lores_image) for lores_image in lores_images]
    current_lores_image_index = 0

    text_fill = "#888"

    while not _event_proc_shutdown.is_set():
        now_time = time.time_ns()
        if (now_time - last_time_frame) / 1000**3 <= (1 / _fps_target):
            # limit max framerate to every ~2ms
            time.sleep(2 / 1000.0)
            continue

        fps = round(1 / (now_time - last_time_frame) * 1000**3, 1)
        last_time_frame = now_time

        # update liveview image every 5 seconds
        if (time.time() - last_time_newimage) > 5:
            # update image every 5 seconds
            current_lores_image_index = random.randint(0, len(lores_images) - 1)
            last_time_newimage = time.time()

        # create PIL image
        img = img_original[current_lores_image_index].copy()

        # add text
        img_draw = ImageDraw.Draw(img)
        font_large = ImageFont.truetype(font=str(path_font), size=50)
        font_small = ImageFont.truetype(font=str(path_font), size=25)

        img_draw.text((25, 400), "virtual camera", fill=text_fill, font=font_large)
        img_draw.text((25, 460), datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"), fill=text_fill, font=font_large)
        img_draw.text((25, 520), f"framerate: {fps}", fill=text_fill, font=font_small)

        # flip if mirror effect is on because messages shall be readable on screen
        if _mirror:
            img = ImageOps.mirror(img)

        # create jpeg
        jpeg_buffer = BytesIO()
        img.save(jpeg_buffer, format="jpeg", quality=90)

        # put jpeg on queue until full. If full this function blocks until queue empty
        with _img_buffer_lock:
            jpeg_bytes = jpeg_buffer.getvalue()
            assert len(jpeg_bytes) < SHARED_MEMORY_BUFFER_BYTES

            compile_buffer(shm, jpeg_bytes)

        with _condition_img_buffer_ready:
            # wait to be notified
            _condition_img_buffer_ready.notify_all()

    logger.info("img_aquisition process finished")
