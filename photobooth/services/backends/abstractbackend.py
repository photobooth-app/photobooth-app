"""
abstract for the photobooth-app backends
"""
import dataclasses
import logging
import time
from abc import ABC, abstractmethod
from functools import cache
from io import BytesIO
from multiprocessing import Condition, Lock, shared_memory
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ...utils.exceptions import ShutdownInProcessError
from ...utils.stoppablethread import StoppableThread
from ..config import appconfig

logger = logging.getLogger(__name__)


#
# Dataclass for stats
#


@dataclasses.dataclass
class BackendStats:
    """
    defines some common stats - if backend supports, they return these properties,
    if not, may be 0 or None
    """

    backend_name: str = __name__
    fps: int = None
    exposure_time_ms: float = None
    lens_position: float = None
    gain: float = None
    lux: float = None
    colour_temperature: int = None
    sharpness: int = None


class AbstractBackend(ABC):
    """
    photobooth-app abstract to create backends.
    """

    @abstractmethod
    def __init__(self):
        self._backendstats: BackendStats = BackendStats(
            backend_name=self.__class__.__name__,
        )
        self._fps = 0
        self._stats_thread = StoppableThread(name="_statsThread", target=self._stats_fun, daemon=True)

        super().__init__()

    def __repr__(self):
        return f"{self.__class__}"

    def stats(self) -> BackendStats:
        self._backendstats.fps = int(round(self._fps, 0))
        return self._backendstats

    def _stats_fun(self):
        # FPS = 1 / time to process loop
        last_calc_time = time.time()  # start time of the loop

        # to calc frames per second every second
        while not self._stats_thread.stopped():
            try:
                self._wait_for_lores_image()  # blocks until new image is avail, we do not ready it here, only calc fps
                self._fps = 1.0 / (time.time() - last_calc_time)
            except (TimeoutError, ZeroDivisionError):
                self._fps = 0

            # store last time
            last_calc_time = time.time()

    @abstractmethod
    def wait_for_hq_image(self):
        """
        function blocks until high quality image is available
        """

    @abstractmethod
    def start(self):
        """To start the backend to serve"""
        self._stats_thread.start()

    @abstractmethod
    def stop(self):
        """To stop the backend to serve"""
        self._stats_thread.stop()
        self._stats_thread.join()

    #
    # INTERNAL FUNCTIONS TO BE IMPLEMENTED
    #

    @abstractmethod
    def _wait_for_lores_image(self):
        """
        function blocks until frame is available for preview stream
        """

    @abstractmethod
    def _on_capture_mode(self):
        """called externally via events and used to change to a capture mode if necessary"""

    @abstractmethod
    def _on_preview_mode(self):
        """called externally via events and used to change to a preview mode if necessary"""

    @staticmethod
    @cache
    def _substitute_image(caption: str = "Error", message: str = "Something happened!", mirror: bool = False) -> bytes:
        """Create a substitute image in case the stream fails.
        The image shall clarify some error occured to the user while trying to recover.

        Args:
            caption (str, optional): Caption in first line. Defaults to "".
            message (str, optional): Additional error message in second line. Defaults to "".
            mirror (bool, optional): Flip left/right in case the stream has mirror effect applied. Defaults to False.

        Returns:
            bytes: _description_
        """
        path_font = Path(__file__).parent.joinpath("assets", "backend_abstract", "fonts", "Roboto-Bold.ttf").resolve()
        text_fill = "#888"

        img = Image.new("RGB", (400, 300), "#ddd")
        img_draw = ImageDraw.Draw(img)
        font_large = ImageFont.truetype(font=str(path_font), size=22)
        font_small = ImageFont.truetype(font=str(path_font), size=15)
        img_draw.text((25, 100), caption, fill=text_fill, font=font_large)
        img_draw.text((25, 120), message, fill=text_fill, font=font_small)
        img_draw.text((25, 140), "please check camera and logs", fill=text_fill, font=font_small)

        # flip if mirror effect is on because messages shall be readable on screen
        if mirror:
            img = ImageOps.mirror(img)

        # create jpeg
        jpeg_buffer = BytesIO()
        img.save(jpeg_buffer, format="jpeg", quality=95)
        return jpeg_buffer.getvalue()

    def wait_for_lores_image(self, retries: int = 10):
        """Function called externally to receivea low resolution image.
        Also used to stream. Tries to recover up to retries times before giving up.

        Args:
            retries (int, optional): How often retry to use the private _wait_for_lores_image function before failing. Defaults to 10.

        Raises:
            exc: Shutdown is handled different, no retry
            exc: All other exceptions will lead to retry before finally fail.

        Returns:
            _type_: _description_
        """
        remaining_retries = retries
        while True:
            try:
                return self._wait_for_lores_image()  # blocks 0.2s usually. 10 retries default wait time=2s
            except ShutdownInProcessError as exc:
                logger.info("ShutdownInProcess, stopping aquisition")
                raise exc
            except Exception as exc:
                if remaining_retries < 0:
                    raise exc

                remaining_retries -= 1
                logger.debug("waiting for backend provide low resolution image...")

                continue

    def gen_stream(self):
        """
        yield jpeg images to stream to client (if not created otherwise)
        this function may be overriden by backends, but this is the default one
        relies on the backends implementation of _wait_for_lores_image to return a buffer
        """
        logger.info(f"livestream started on backend {self=}")

        last_time = time.time_ns()
        while True:
            now_time = time.time_ns()
            if (now_time - last_time) / 1000**3 >= (1 / appconfig.backends.LIVEPREVIEW_FRAMERATE):
                last_time = now_time

                try:
                    output_jpeg_bytes = self.wait_for_lores_image()
                except ShutdownInProcessError:
                    logger.info("ShutdownInProcess, stopping stream")
                    return
                except TimeoutError:
                    # this error could be recovered (example: DSLR turned off/on again)
                    logger.error("error capture lores image for stream. timeout expired, retrying")
                    # can we do additional error handling here?
                    output_jpeg_bytes = self._substitute_image(
                        "Oh no - stream error :(",
                        "timeout, no preview from cam. retrying.",
                        appconfig.uisettings.livestream_mirror_effect,
                    )
                except Exception as exc:
                    # this error probably cannot recover.
                    logger.exception(exc)
                    logger.error(f"streaming exception: {exc}")
                    output_jpeg_bytes = self._substitute_image(
                        "Oh no - stream error :(",
                        "exception, unknown error getting preview.",
                        appconfig.uisettings.livestream_mirror_effect,
                    )

                yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + output_jpeg_bytes + b"\r\n\r\n")


#
# INTERNAL FUNCTIONS to operate on the shared memory exchanged between processes.
#


@dataclasses.dataclass
class SharedMemoryDataExch:
    """
    bundle data array and it's condition.
    1) save some instance attributes and
    2) bundle as it makes sense
    """

    sharedmemory: shared_memory.SharedMemory = None
    condition: Condition = None
    lock: Lock = None


def decompile_buffer(shm: memoryview) -> bytes:
    """
    decompile buffer holding jpeg buffer for transport between processes
    in shared memory
    constructed as
    INT(4bytes)+JPEG of length the int describes

    Args:
        shm (memoryview): shared memory buffer

    Returns:
        bytes: concat(length of jpeg+jpegbuffer)
    """
    # ATTENTION: shm is a memoryview; sliced variables are also a reference only.
    # means for this app in consequence: here is the place to make a copy
    # of the image for further processing
    # ATTENTION2: this function needs to be called with lock aquired
    length = int.from_bytes(shm.buf[0:4], "big")
    ret: memoryview = shm.buf[4 : length + 4]
    return ret.tobytes()


def compile_buffer(shm: memoryview, jpeg_buffer: bytes) -> bytes:
    """
    compile buffer holding jpeg buffer for transport between processes
    in shared memory
    constructed as
    INT(4bytes)+JPEG of length the int describes

    Args:
        shm (bytes): shared memory buffer
        jpeg_buffer (bytes): jpeg image
    """
    # ATTENTION: shm is a memoryview; sliced variables are also a reference only.
    # means for this app in consequence: here is the place to make a copy
    # of the image for further processing
    # ATTENTION2: this function needs to be called with lock aquired
    length: int = len(jpeg_buffer)
    length_bytes = length.to_bytes(4, "big")
    shm.buf[0:4] = length_bytes
    shm.buf[4 : length + 4] = jpeg_buffer
