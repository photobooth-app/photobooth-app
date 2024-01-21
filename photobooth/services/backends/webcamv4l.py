"""
v4l webcam implementation backend
"""
import logging
from multiprocessing import Condition, Event, Lock, Process, shared_memory

from v4l2py import Device, VideoCapture  # type: ignore

from ..config import AppConfig, appconfig
from .abstractbackend import AbstractBackend, SharedMemoryDataExch, compile_buffer, decompile_buffer

SHARED_MEMORY_BUFFER_BYTES = 15 * 1024**2

logger = logging.getLogger(__name__)


class WebcamV4lBackend(AbstractBackend):
    """_summary_

    Args:
        AbstractBackend (_type_): _description_
    """

    def __init__(self):
        super().__init__()
        self._failing_wait_for_lores_image_is_error = True  # missing lores images is automatically considered as error

        self._img_buffer: SharedMemoryDataExch = SharedMemoryDataExch(
            sharedmemory=shared_memory.SharedMemory(create=True, size=SHARED_MEMORY_BUFFER_BYTES),
            condition=Condition(),
            lock=Lock(),
        )
        self._event_proc_shutdown: Event = Event()
        self._v4l_process: Process = None

    def __del__(self):
        try:
            if self._img_buffer:
                self._img_buffer.sharedmemory.close()
                self._img_buffer.sharedmemory.unlink()
        except Exception as exc:
            # cant use logger any more, just to have some logs to debug if exception
            print(exc)
            print("error deconstructing shared memory")

    def _device_start(self):
        """To start the v4l acquisition process"""
        # start camera
        self._event_proc_shutdown.clear()

        logger.info(f"starting webcam process, {appconfig.backends.v4l_device_index=}")

        self._v4l_process = Process(
            target=v4l_img_aquisition,
            name="WebcamV4lAquisitionProcess",
            args=(
                self._img_buffer.sharedmemory.name,
                self._img_buffer.condition,
                self._img_buffer.lock,
                # need to pass config, because unittests can change config,
                # if not passed, the config are not available in the separate process!
                appconfig,
                self._event_proc_shutdown,
            ),
            daemon=True,
        )

        self._v4l_process.start()

        # block until startup completed, this ensures tests work well and backend for sure delivers images if requested
        try:
            self.wait_for_lores_image(60)
        except Exception as exc:
            raise RuntimeError("failed to start up backend") from exc

        logger.debug(f"{self.__module__} started")

    def _device_stop(self):
        # signal process to shutdown properly
        self._event_proc_shutdown.set()

        # wait until shutdown finished
        if self._v4l_process and self._v4l_process.is_alive():
            self._v4l_process.join()
            self._v4l_process.close()

        logger.debug(f"{self.__module__} stopped")

    def _device_available(self):
        """
        For v4l we check to open device is possible
        """
        return is_valid_camera_index(appconfig.backends.v4l_device_index)

    def _wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""

        # get img off the producing queue
        with self._img_buffer.condition:
            if not self._img_buffer.condition.wait(timeout=4):
                raise TimeoutError("timeout receiving frames")

            with self._img_buffer.lock:
                img = decompile_buffer(self._img_buffer.sharedmemory)

        return img

    #
    # INTERNAL FUNCTIONS
    #
    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""

        with self._img_buffer.condition:
            if not self._img_buffer.condition.wait(timeout=0.2):
                raise TimeoutError("timeout receiving frames")

            with self._img_buffer.lock:
                img = decompile_buffer(self._img_buffer.sharedmemory)
            return img

    def _on_configure_optimized_for_hq_capture(self):
        pass

    def _on_configure_optimized_for_idle(self):
        pass

    #
    # INTERNAL IMAGE GENERATOR
    #


def v4l_img_aquisition(
    shm_buffer_name,
    _condition_img_buffer_ready: Condition,
    _img_buffer_lock: Lock,
    _config: AppConfig,
    _event_proc_shutdown: Event,
):
    """_summary_

    Raises:
        exc: _description_

    Returns:
        _type_: _description_
    """
    # init
    ## Create a logger. INFO: this logger is in separate process and just logs to console.
    # Could be replaced in future by a more sophisticated solution
    logger = logging.getLogger()
    fmt = "%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s) proc%(process)d"
    logging.basicConfig(level=logging.DEBUG, format=fmt)

    shm = shared_memory.SharedMemory(shm_buffer_name)

    with Device.from_id(_config.backends.v4l_device_index) as device:
        logger.info(f"webcam devices index {_config.backends.v4l_device_index} opened")
        logger.info(f"webcam info: {device.info.card}")

        try:
            capture = VideoCapture(device)
            capture.set_format(_config.backends.v4l_CAM_RESOLUTION_WIDTH, _config.backends.v4l_CAM_RESOLUTION_HEIGHT, "MJPG")
        except (AttributeError, FileNotFoundError) as exc:
            logger.error(f"cannot open camera {_config.backends.v4l_device_index} properly.")
            logger.exception(exc)
            raise exc

        for frame in device:  # forever
            # put jpeg on queue until full. If full this function blocks until queue empty
            with _img_buffer_lock:
                compile_buffer(shm, bytes(frame))

            with _condition_img_buffer_ready:
                # wait to be notified
                _condition_img_buffer_ready.notify_all()

            # abort streaming on shutdown so process can join and close
            if _event_proc_shutdown.is_set():
                break

    logger.info("v4l_img_aquisition finished, exit")


def available_camera_indexes():
    """
    detect usb camera indexes

    Returns:
        _type_: _description_
    """
    # checks the first 10 indexes.

    index = 0
    arr = []
    i = 10
    while i > 0:
        if is_valid_camera_index(index):
            arr.append(index)
        index += 1
        i -= 1

    return arr


def is_valid_camera_index(index):
    """test whether index is valid device

    Args:
        index (_type_): _description_

    Returns:
        _type_: _description_
    """
    try:
        with Device.from_id(index) as device:
            capture = VideoCapture(device)
            capture.set_format(640, 480, "MJPG")

            for _ in device:
                # got frame, close cam and return true; otherwise false.
                break

            return True

    except Exception:
        return False
