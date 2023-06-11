"""
v4l webcam implementation backend
"""
import logging
from multiprocessing import Condition, Event, Lock, Process, shared_memory

from pymitter import EventEmitter

from ...appconfig import AppConfig
from ...utils.exceptions import ShutdownInProcessError
from .abstractbackend import (
    AbstractBackend,
    BackendStats,
    SharedMemoryDataExch,
    compile_buffer,
    decompile_buffer,
)

try:
    from v4l2py import Device
except Exception as import_exc:
    raise OSError("v4l2py import error; check v4l2py installation") from import_exc

SHARED_MEMORY_BUFFER_BYTES = 15 * 1024**2

logger = logging.getLogger(__name__)


class WebcamV4lBackend(AbstractBackend):
    """_summary_

    Args:
        AbstractBackend (_type_): _description_
    """

    def __init__(self, evtbus: EventEmitter, config: AppConfig):
        """_summary_

        Args:
            evtbus (EventEmitter): _description_
            config (AppConfig): _description_
        """
        super().__init__(evtbus, config)
        # public props (defined in abstract class also)
        self.metadata = {}

        # private props
        self._evtbus = evtbus
        self._config = config

        self._img_buffer: SharedMemoryDataExch = None
        self._event_proc_shutdown: Event = Event()
        self._v4l_process: Process = None

        self._on_preview_mode()

    def start(self):
        """To start the v4l acquisition process"""
        # start camera
        self._event_proc_shutdown.clear()

        self._img_buffer: SharedMemoryDataExch = SharedMemoryDataExch(
            sharedmemory=shared_memory.SharedMemory(create=True, size=SHARED_MEMORY_BUFFER_BYTES),
            condition=Condition(),
            lock=Lock(),
        )

        logger.info(f"starting webcam process, {self._config.backends.v4l_device_index=}")

        self._v4l_process = Process(
            target=v4l_img_aquisition,
            name="WebcamV4lAquisitionProcess",
            args=(
                self._img_buffer.sharedmemory.name,
                self._img_buffer.condition,
                self._img_buffer.lock,
                # need to pass config, because unittests can change config,
                # if not passed, the config are not available in the separate process!
                self._config,
                self._event_proc_shutdown,
            ),
            daemon=True,
        )

        self._v4l_process.start()

        # block until startup completed, this ensures tests work well and backend for sure delivers images if requested
        remaining_retries = 10
        while True:
            with self._img_buffer.condition:
                if self._img_buffer.condition.wait(timeout=0.5):
                    break

                if remaining_retries < 0:
                    raise RuntimeError("failed to start up backend")

                remaining_retries -= 1
                logger.info("waiting for backend to start up...")

        logger.debug(f"{self.__module__} started")

    def stop(self):
        # signal process to shutdown properly
        self._event_proc_shutdown.set()

        # wait until shutdown finished
        self._v4l_process.join(timeout=5)
        self._v4l_process.close()

        self._img_buffer.sharedmemory.close()
        self._img_buffer.sharedmemory.unlink()

        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        self._evtbus.emit("frameserver/onCapture")

        # get img off the producing queue
        with self._img_buffer.condition:
            if not self._img_buffer.condition.wait(timeout=4):
                raise TimeoutError("timeout receiving frames")

            with self._img_buffer.lock:
                img = decompile_buffer(self._img_buffer.sharedmemory)

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

    def _wait_for_lores_frame(self):
        """autofocus not supported by this backend"""
        raise NotImplementedError()

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""

        if self._event_proc_shutdown.is_set():
            raise ShutdownInProcessError("shutdown already in progress, abort early")

        with self._img_buffer.condition:
            if not self._img_buffer.condition.wait(timeout=4):
                raise TimeoutError("timeout receiving frames")

            with self._img_buffer.lock:
                img = decompile_buffer(self._img_buffer.sharedmemory)
            return img

    def _on_capture_mode(self):
        logger.debug("change to capture mode requested - ignored on this backend")

    def _on_preview_mode(self):
        logger.debug("change to preview mode requested - ignored on this backend")

    #
    # INTERNAL IMAGE GENERATOR
    #


def v4l_img_aquisition(
    shm_buffer_name,
    _condition_img_buffer_ready: Condition,
    _img_buffer_lock: Lock,
    _config,
    _event_proc_shutdown: Event,
):
    """_summary_

    Raises:
        exc: _description_

    Returns:
        _type_: _description_
    """
    # init
    shm = shared_memory.SharedMemory(shm_buffer_name)

    with Device.from_id(_config.backends.v4l_device_index) as cam:
        logger.info(f"webcam devices index {_config.backends.v4l_device_index} opened")
        try:
            cam.video_capture.set_format(
                _config.common.CAPTURE_CAM_RESOLUTION_WIDTH,
                _config.common.CAPTURE_CAM_RESOLUTION_HEIGHT,
                "MJPG",
            )
        except (AttributeError, FileNotFoundError) as exc:
            logger.error(f"cannot open camera {_config.backends.v4l_device_index} properly.")
            logger.exception(exc)
            raise exc

        for jpeg_buffer in cam:  # forever
            # put jpeg on queue until full. If full this function blocks until queue empty
            with _img_buffer_lock:
                compile_buffer(shm, jpeg_buffer)

            with _condition_img_buffer_ready:
                # wait to be notified
                _condition_img_buffer_ready.notify_all()

            # abort streaming on shutdown so process can join and close
            if _event_proc_shutdown.is_set():
                break


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
        cap = Device.from_id(index)
        cap.video_capture.set_format(640, 480, "MJPG")
        for _ in cap:
            # got frame, close cam and return true; otherwise false.
            break
        cap.close()
    except (AttributeError, FileNotFoundError, OSError):
        return False

    return True
