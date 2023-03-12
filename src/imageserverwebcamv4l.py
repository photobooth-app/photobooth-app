"""
v4l webcam implementation backend
"""
import time
import logging
from multiprocessing import Process, shared_memory, Condition, Lock
from pymitter import EventEmitter
from src.imageserverabstract import (
    ImageServerAbstract,
    decompile_buffer,
    compile_buffer,
    SharedMemoryDataExch,
)
from src.configsettings import settings

try:
    from v4l2py import Device
except ImportError as import_exc:
    raise OSError("backend v4l2py not supported on windows platform") from import_exc

logger = logging.getLogger(__name__)


class ImageServerWebcamV4l(ImageServerAbstract):
    """_summary_

    Args:
        ImageServerAbstract (_type_): _description_
    """

    def __init__(self, evtbus: EventEmitter, enable_stream):
        super().__init__(evtbus, enable_stream)
        # public props (defined in abstract class also)
        self.exif_make = "Photobooth WebcamV4l"
        self.exif_model = "Custom"
        self.metadata = {}

        # private props
        self._evtbus = evtbus

        self._img_buffer: SharedMemoryDataExch = SharedMemoryDataExch(
            sharedmemory=shared_memory.SharedMemory(
                create=True,
                size=settings._shared_memory_buffer_size,  # pylint: disable=protected-access
            ),
            condition=Condition(),
            lock=Lock(),
        )

        self._v4l_process = Process(
            target=v4l_img_aquisition,
            name="ImageServerWebcamV4lAquisitionProcess",
            args=(
                self._img_buffer.sharedmemory.name,
                self._img_buffer.condition,
                self._img_buffer.lock,
                # need to pass settings, because unittests can change settings,
                # if not passed, the settings are not available in the separate process!
                settings,
            ),
            daemon=True,
        )

        self._on_preview_mode()

    def start(self):
        """To start the v4l acquisition process"""
        # start camera

        self._v4l_process.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        self._img_buffer.sharedmemory.close()
        self._img_buffer.sharedmemory.unlink()

        self._v4l_process.terminate()
        self._v4l_process.join(1)
        self._v4l_process.close()

        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        self._evtbus.emit("frameserver/onCapture")

        # get img off the producing queue
        with self._img_buffer.condition:
            if not self._img_buffer.condition.wait(2):
                raise IOError("timeout receiving frames")

            with self._img_buffer.lock:
                img = decompile_buffer(self._img_buffer.sharedmemory)

        self._evtbus.emit("frameserver/onCaptureFinished")

        # return to previewmode
        self._on_preview_mode()

        return img

    def trigger_hq_capture(self):
        self._on_capture_mode()

    #
    # INTERNAL FUNCTIONS
    #

    def _wait_for_lores_frame(self):
        """autofocus not supported by this backend"""
        raise NotImplementedError()

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""
        with self._img_buffer.condition:
            if not self._img_buffer.condition.wait(2):
                raise IOError("timeout receiving frames")

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
    _settings,
):
    """_summary_

    Raises:
        exc: _description_

    Returns:
        _type_: _description_
    """
    # init
    shm = shared_memory.SharedMemory(shm_buffer_name)

    with Device.from_id(_settings.backends.v4l_device_index) as cam:
        logger.info(
            f"webcam devices index {_settings.backends.v4l_device_index} opened"
        )
        try:
            cam.video_capture.set_format(
                _settings.common.CAPTURE_CAM_RESOLUTION_WIDTH,
                _settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT,
                "MJPG",
            )
        except (AttributeError, FileNotFoundError) as exc:
            logger.error(
                f"cannot open camera {_settings.backends.v4l_device_index} properly."
            )
            logger.exception(exc)
            raise exc

        for jpeg_buffer in cam:  # forever
            time.sleep(0.1)

            # put jpeg on queue until full. If full this function blocks until queue empty
            with _img_buffer_lock:
                compile_buffer(shm, jpeg_buffer)

            with _condition_img_buffer_ready:
                # wait to be notified
                _condition_img_buffer_ready.notify_all()


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
    except (AttributeError, FileNotFoundError):
        return False

    return True
