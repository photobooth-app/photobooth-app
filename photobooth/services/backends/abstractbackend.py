"""
abstract for the photobooth-app backends
"""
import dataclasses
import logging
import time
from abc import ABC, abstractmethod
from multiprocessing import Condition, Lock, shared_memory

from ...utils.exceptions import ShutdownInProcessError
from ...utils.stoppablethread import StoppableThread

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
        # statisitics attributes
        self._backendstats: BackendStats = BackendStats(backend_name=self.__class__.__name__)
        self._fps = 0
        self._stats_thread: StoppableThread = None

        # (re)connect supervisor attributes
        self._device_connected = None
        self._connect_thread: StoppableThread = None

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
            except (TimeoutError, ZeroDivisionError, AttributeError, ValueError):  # AttributeError and ValueError for disabled backend
                self._fps = 0

            # store last time
            last_calc_time = time.time()

    def _connect_fun(self):
        self._device_connected = False

        while not self._connect_thread.stopped():  # repeat until stopped
            # try to reconnect

            # if connected, busy waiting
            if self._device_connected:
                time.sleep(1)
                continue

            # if not connected, check for device availability
            if not self._device_available():
                logger.error("device not available to (re)connect to, retrying")
            else:
                # device available, start the backends local functions
                try:
                    self._device_start()
                    self._device_connected = True
                except Exception as exc:
                    logger.exception(exc)
                    logger.critical("camera failed to initialize. no power? no connection?")

            time.sleep(1)

        # supervising connection thread was asked to stop - so we ask device to do the sam
        logger.info("exit connection function, stopping device")
        self._device_stop()

    @abstractmethod
    def wait_for_hq_image(self):
        """
        function blocks until high quality image is available
        """

    def start(self):
        """To start the backend to serve"""
        # statistics
        self._stats_thread = StoppableThread(name="_statsThread", target=self._stats_fun, daemon=True)
        self._stats_thread.start()

        # (re)connect supervisor
        self._connect_thread = StoppableThread(name="_connect_thread", target=self._connect_fun, daemon=True)
        self._connect_thread.start()

    def stop(self):
        """To stop the backend to serve"""

        if self._connect_thread and self._connect_thread.is_alive():
            self._connect_thread.stop()
            self._connect_thread.join()

        if self._stats_thread and self._stats_thread.is_alive():
            self._stats_thread.stop()
            self._stats_thread.join()

        # and continue inform the reconnect thread.

    #
    # INTERNAL FUNCTIONS TO BE IMPLEMENTED
    #

    @abstractmethod
    def _device_start(self):
        """
        start the device ()
        """

    @abstractmethod
    def _device_stop(self):
        """
        start the device ()
        """

    @abstractmethod
    def _device_available(self) -> bool:
        """
        start the device ()
        """

    def _device_disconnected(self):
        self._device_stop()
        self._device_connected = False

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
