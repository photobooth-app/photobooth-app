"""
backend opencv2 for webcameras
"""

import logging
import platform
import time
from multiprocessing import Condition, Event, Lock, Process, shared_memory

import cv2
from turbojpeg import TurboJPEG

from ..config.groups.backends import GroupBackendOpenCv2
from .abstractbackend import AbstractBackend, SharedMemoryDataExch, compile_buffer, decompile_buffer

SHARED_MEMORY_BUFFER_BYTES = 15 * 1024**2

logger = logging.getLogger(__name__)
turbojpeg = TurboJPEG()


class WebcamCv2Backend(AbstractBackend):
    """
    opencv2 backend implementation for webcameras
    """

    def __init__(self, config: GroupBackendOpenCv2):
        self._config: GroupBackendOpenCv2 = config
        super().__init__()

        self._failing_wait_for_lores_image_is_error = True  # missing lores images is automatically considered as error

        self._img_buffer = SharedMemoryDataExch(
            sharedmemory=shared_memory.SharedMemory(
                create=True,
                size=SHARED_MEMORY_BUFFER_BYTES,
            ),
            condition=Condition(),
            lock=Lock(),
        )

        self._event_proc_shutdown: Event = Event()

        self._cv2_process: Process = None

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
        """To start the cv2 acquisition process"""

        self._event_proc_shutdown.clear()

        self._cv2_process = Process(
            target=cv2_img_aquisition,
            name="WebcamCv2AquisitionProcess",
            args=(
                self._img_buffer.sharedmemory.name,
                self._img_buffer.lock,
                self._img_buffer.condition,
                self._config,
                self._event_proc_shutdown,
            ),
            daemon=True,
        )
        self._cv2_process.start()

        time.sleep(1)

        # wait until threads are up and deliver images actually. raises exceptions if fails after several retries
        self._block_until_delivers_lores_images()

        logger.debug(f"{self.__module__} started")

    def _device_stop(self):
        # signal process to shutdown properly
        self._event_proc_shutdown.set()

        # wait until shutdown finished
        if self._cv2_process and self._cv2_process.is_alive():
            self._cv2_process.join()
            self._cv2_process.close()

        logger.debug(f"{self.__module__} stopped")

    def _device_available(self):
        """
        For cv2 we check to open device is possible
        """
        device = cv2.VideoCapture(self._config.device_index)
        ret, array = device.read()  # ret True if connected properly, otherwise False
        if ret:
            device.release()

        return ret

    def _wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        return self._wait_for_lores_image()

    #
    # INTERNAL FUNCTIONS
    #

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""

        with self._img_buffer.condition:
            if not self._img_buffer.condition.wait(timeout=0.5):
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


def cv2_img_aquisition(
    shm_buffer_name,
    _img_buffer_lock,
    _condition_img_buffer_ready: Condition,
    # need to pass config, because unittests can change config,
    # if not passed, the config are not available in the separate process!
    _config: GroupBackendOpenCv2,
    _event_proc_shutdown: Event,
):
    """
    process function to gather webcam images
    """
    # init
    ## Create a logger. INFO: this logger is in separate process and just logs to console.
    # Could be replaced in future by a more sophisticated solution
    logger = logging.getLogger()
    fmt = "%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s) proc%(process)d"
    logging.basicConfig(level=logging.DEBUG, format=fmt)

    shm = shared_memory.SharedMemory(shm_buffer_name)

    if platform.system() == "Windows":
        logger.info("force VideoCapture to DSHOW backend on windows (MSMF is buggy and crashes app)")
        _video = cv2.VideoCapture(_config.device_index, cv2.CAP_DSHOW)
    else:
        _video = cv2.VideoCapture(_config.device_index)

    # activate preview mode on init
    _video_set_check(_video, cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    _video_set_check(_video, cv2.CAP_PROP_FPS, 30.0)
    _video_set_check(_video, cv2.CAP_PROP_FRAME_WIDTH, _config.CAM_RESOLUTION_WIDTH)
    _video_set_check(_video, cv2.CAP_PROP_FRAME_HEIGHT, _config.CAM_RESOLUTION_HEIGHT)

    if not _video.isOpened():
        raise OSError(f"cannot open camera index {_config.device_index}")

    if not _video.read()[0]:
        raise OSError(f"cannot read camera index {_config.device_index}")

    logger.info(f"webcam cv2 using backend {_video.getBackendName()}")
    logger.info(f"webcam resolution: {int(_video.get(cv2.CAP_PROP_FRAME_WIDTH))}x" f"{int(_video.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

    # read first five frames and send to void
    for _ in range(5):
        _, _ = _video.read()

    while not _event_proc_shutdown.is_set():
        ret, array = _video.read()
        # ret=True successful read, otherwise False?
        if not ret:
            raise OSError("error reading camera frame")

        # apply flip image to stream only:
        if _config.CAMERA_TRANSFORM_HFLIP:
            array = cv2.flip(array, 1)
        if _config.CAMERA_TRANSFORM_VFLIP:
            array = cv2.flip(array, 0)

        # preview livestream
        jpeg_buffer = turbojpeg.encode(array, quality=90)
        # put jpeg on queue until full. If full this function blocks until queue empty
        with _img_buffer_lock:
            compile_buffer(shm, jpeg_buffer)

        with _condition_img_buffer_ready:
            # wait to be notified
            _condition_img_buffer_ready.notify_all()

    # release camera on process shutdown
    _video.release()

    logger.info("cv2_img_aquisition finished, exit")


def _video_set_check(_video, prop, value):
    ret = _video.set(prop, value)
    if ret is True:
        logger.info(f"set {prop=} {value} successful")
    else:
        logger.error(f"error setting {prop=} {value}")


def available_camera_indexes():
    """
    detect device indexes with usb camera connected

    Returns:
        _type_: _description_
    """
    # checks the first 10 indexes.

    index = 0
    arr = []
    i = 10
    while i > 0:
        cap = cv2.VideoCapture(index)
        if cap.read()[0]:
            arr.append(index)
            cap.release()
        index += 1
        i -= 1

    return arr
