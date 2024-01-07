"""
abstract for the photobooth-app backends
"""
import dataclasses
import logging
import os
import time
from abc import ABC, abstractmethod
from enum import Enum, auto
from multiprocessing import Condition, Lock, shared_memory

from ...utils.stoppablethread import StoppableThread

logger = logging.getLogger(__name__)


class EnumDeviceStatus(Enum):
    """enum for device status"""

    initialized = auto()
    starting = auto()
    running = auto()
    stopping = auto()
    stopped = auto()
    fault = auto()
    # halt = auto()


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
        self._device_status: EnumDeviceStatus = EnumDeviceStatus.initialized
        # concrete backend implementation can signal using this flag there is an error and it needs restart.
        self._device_status_fault_flag: bool = False
        # only for (webcam, picam and virtualcamera) error can detected by missing lores img
        self._failing_wait_for_lores_image_is_error: bool = False
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
            except Exception:
                # suffer in silence. If any issue occured assume the FPS is 0
                self._fps = 0

            # store last time
            last_calc_time = time.time()

    @property
    def device_status(self) -> EnumDeviceStatus:
        return self._device_status

    @device_status.setter
    def device_status(self, value: EnumDeviceStatus):
        logger.info(f"setting device status from {self._device_status.name} to {value.name}")
        self._device_status = value

    def _connect_fun(self):
        while not self._connect_thread.stopped():  # repeat until stopped # try to reconnect
            # is running but problem detected!
            if self.device_status is EnumDeviceStatus.running and self._device_status_fault_flag is True:
                logger.info("implementation signaled a fault during run! set status to fault and try to recover.")
                self._device_status_fault_flag = False  # clear the flag
                self.device_status = EnumDeviceStatus.fault
                try:
                    self._device_stop()
                except Exception as exc:
                    logger.error(f"error stopping faulty backend {exc}, still trying to recover")

            # if running or stopping, busy waiting
            if self.device_status in (EnumDeviceStatus.running, EnumDeviceStatus.stopping):
                time.sleep(1)  # abort processing in these states, still need to delay
                continue

            if self.device_status in (EnumDeviceStatus.initialized, EnumDeviceStatus.stopped, EnumDeviceStatus.fault):
                logger.info(f"connect_thread device status={self.device_status}, so trying to start")
                self.device_status = EnumDeviceStatus.starting

            # if not connected, check for device availability as long as not requested to shut down.
            if self.device_status is EnumDeviceStatus.starting and not self._connect_thread.stopped():
                logger.info("trying to start backend")
                try:
                    # device available, start the backends local functions
                    if self._device_available():
                        logger.info("device is available")
                        self._device_start()
                        # when _device_start is finished, the device needs to be up and running, access allowed.
                        # signal that the device can be used externally in general.
                        self.device_status = EnumDeviceStatus.running
                        logger.info("device started, set status running")
                    else:
                        logger.error("device not available to (re)connect to, retrying")
                        # status remains starting, so in next loop it retries.
                        try:
                            self._device_stop()
                        except Exception as exc:
                            logger.error(f"error stopping faulty backend {exc}, still trying to recover")

                except Exception as exc:
                    logger.exception(exc)
                    logger.critical("camera failed to initialize. no power? no connection?")
                    self.device_status = EnumDeviceStatus.fault

            time.sleep(1)
            # next after wait is to check if connect_thread is stopped - in this case no further actions.
            # means: sleep has to be last statement in while loop

        # supervising connection thread was asked to stop - so we ask device to do the sam
        logger.info("exit connection function, stopping device")
        self._device_stop()

    def start(self):
        """To start the backend to serve"""
        # statistics
        self._stats_thread = StoppableThread(name="_statsThread", target=self._stats_fun, daemon=True)
        self._stats_thread.start()

        # (re)connect supervisor
        self._connect_thread = StoppableThread(name="_connect_thread", target=self._connect_fun, daemon=True)
        self._connect_thread.start()

        if "PYTEST_CURRENT_TEST" in os.environ:
            # in pytest we need to wait for the connect thread properly set up the device.
            # if we do not wait, the test is over before the backend is acutually ready to deliver frames and might fail.
            # in reality this is not an issue
            logger.info("test environment detected, blocking until backend started")
            self.block_until_device_is_running()
            logger.info("backend started, finished blocking")

    def stop(self):
        """To stop the backend to serve"""

        if self._connect_thread and self._connect_thread.is_alive():
            self._connect_thread.stop()
            self._connect_thread.join()

        if self._stats_thread and self._stats_thread.is_alive():
            self._stats_thread.stop()
            self._stats_thread.join()

    def block_until_device_is_running(self):
        """Mostly used for testing to ensure the device is up.

        Returns:
            _type_: _description_
        """
        while self.device_status is not EnumDeviceStatus.running:
            logger.info("waiting")
            time.sleep(0.2)

        logger.info("device status is running now")

    def device_set_status_fault_flag(self):
        logger.info("set _device_status_fault_flag to True to signal the device needs to be recovered.")
        self._device_status_fault_flag = True

    def wait_for_hq_image(self, retries: int = 3) -> bytes:
        """
        function blocks until high quality image is available
        """

        for attempt in range(1, retries + 1):
            try:
                return self._wait_for_hq_image()
            except Exception as exc:
                logger.exception(exc)
                logger.error(f"error capture image. {attempt=}/{retries}, retrying")
                continue

        else:
            # we failed finally all the attempts - deal with the consequences.
            self.device_set_status_fault_flag()
            logger.critical(f"finally failed after {retries} attempts to capture image!")
            raise RuntimeError(f"finally failed after {retries} attempts to capture image!")

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

        for attempt in range(1, retries):
            try:
                return self._wait_for_lores_image()  # blocks 0.2s usually. 10 retries default wait time=2s
            except TimeoutError:
                # if timeout occured it will retry several attempts more before finally fail (else of for below)
                logger.debug(f"device timed out deliver lores image ({attempt}/{retries}).")
                if self._connect_thread.stopped():
                    raise StopIteration("backend is shutting down") from None  # allows calling function to stop requesting images if app shuts down
                else:
                    continue
            except Exception as exc:
                # other exceptions fail immediately
                logger.warning("device raised exception (maybe lost connection to device?)")
                raise RuntimeError("device raised exception (maybe lost connection to device?)") from exc

        # final call
        try:
            return self._wait_for_lores_image()  # blocks 0.2s usually. 10 retries default wait time=2s
        except Exception as exc:
            # we failed finally all the attempts - deal with the consequences.
            logger.exception(exc)
            logger.critical(f"finally failed after {retries} attempts to capture lores image!")

            if self._failing_wait_for_lores_image_is_error:
                logger.error("failing to get lores images from device is considered as error, set fault flag to recover.")
                self.device_set_status_fault_flag()

            raise RuntimeError("device raised exception") from exc

    #
    # ABSTRACT METHODS TO BE IMPLEMENTED BY CONCRETE BACKEND (cv2, v4l, ...)
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

    @abstractmethod
    def _wait_for_hq_image(self):
        """
        function blocks until image still is available
        """

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
