"""
backend opencv2 for webcameras
"""
import logging
import platform
from multiprocessing import Condition, Event, Lock, Process, shared_memory

import cv2
from pymitter import EventEmitter
from turbojpeg import TurboJPEG

from ...appconfig import AppConfig
from ...utils.exceptions import ShutdownInProcessError
from .abstractbackend import (
    AbstractBackend,
    BackendStats,
    SharedMemoryDataExch,
    compile_buffer,
    decompile_buffer,
)

SHARED_MEMORY_BUFFER_BYTES = 15 * 1024**2

logger = logging.getLogger(__name__)
turbojpeg = TurboJPEG()


class WebcamCv2Backend(AbstractBackend):
    """
    opencv2 backend implementation for webcameras
    """

    def __init__(self, evtbus: EventEmitter, config: AppConfig):
        super().__init__(evtbus, config)
        # public props (defined in abstract class also)
        self.metadata = {}

        # private props
        self._evtbus = evtbus
        self._config = config

        self._img_buffer_lores: SharedMemoryDataExch = None
        self._img_buffer_hires: SharedMemoryDataExch = None
        self._event_hq_capture: Event = Event()
        self._event_proc_shutdown: Event = Event()

        self._cv2_process: Process = None

        self._on_preview_mode()

    def start(self):
        """To start the cv2 acquisition process"""
        # start camera

        self._event_proc_shutdown.clear()

        self._img_buffer_lores = SharedMemoryDataExch(
            sharedmemory=shared_memory.SharedMemory(
                create=True,
                size=SHARED_MEMORY_BUFFER_BYTES,
            ),
            condition=Condition(),
            lock=Lock(),
        )
        self._img_buffer_hires = SharedMemoryDataExch(
            sharedmemory=shared_memory.SharedMemory(
                create=True,
                size=SHARED_MEMORY_BUFFER_BYTES,
            ),
            condition=Condition(),
            lock=Lock(),
        )

        self._cv2_process = Process(
            target=cv2_img_aquisition,
            name="WebcamCv2AquisitionProcess",
            args=(
                self._img_buffer_lores.sharedmemory.name,
                self._img_buffer_hires.sharedmemory.name,
                self._img_buffer_lores.lock,
                self._img_buffer_hires.lock,
                self._event_hq_capture,
                self._img_buffer_lores.condition,
                self._img_buffer_hires.condition,
                self._config,
                self._event_proc_shutdown,
            ),
            daemon=True,
        )
        self._cv2_process.start()

        # block until startup completed, this ensures tests work well and backend for sure delivers images if requested
        remaining_retries = 16
        while True:
            with self._img_buffer_lores.condition:
                if self._img_buffer_lores.condition.wait(timeout=0.5):
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
        self._cv2_process.join(timeout=5)
        self._cv2_process.close()

        self._img_buffer_lores.sharedmemory.close()
        self._img_buffer_lores.sharedmemory.unlink()
        self._img_buffer_hires.sharedmemory.close()
        self._img_buffer_hires.sharedmemory.unlink()

        logger.debug(f"{self.__module__} stopped")

    def wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""
        self._evtbus.emit("frameserver/onCapture")

        # get img off the producing queue
        with self._img_buffer_hires.condition:
            self._event_hq_capture.set()

            if not self._img_buffer_hires.condition.wait(timeout=4):
                raise TimeoutError("timeout receiving frames")

            with self._img_buffer_hires.lock:
                img = decompile_buffer(self._img_buffer_hires.sharedmemory)

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

        with self._img_buffer_lores.condition:
            if not self._img_buffer_lores.condition.wait(timeout=4):
                raise TimeoutError("timeout receiving frames")

            with self._img_buffer_lores.lock:
                img = decompile_buffer(self._img_buffer_lores.sharedmemory)
            return img

    def _on_capture_mode(self):
        logger.debug("change to capture mode requested - ignored for cv2 backend")

    def _on_preview_mode(self):
        logger.debug("change to preview mode requested - ignored for cv2 backend")


#
# INTERNAL IMAGE GENERATOR
#


def cv2_img_aquisition(
    shm_buffer_lores_name,
    shm_buffer_hires_name,
    _img_buffer_lores_lock,
    _img_buffer_hires_lock,
    _event_hq_capture: Event,
    _condition_img_buffer_lores_ready: Condition,
    _condition_img_buffer_hires_ready: Condition,
    # need to pass config, because unittests can change config,
    # if not passed, the config are not available in the separate process!
    _config,
    _event_proc_shutdown: Event,
):
    """
    process function to gather webcam images
    """
    # init

    shm_lores = shared_memory.SharedMemory(shm_buffer_lores_name)
    shm_hires = shared_memory.SharedMemory(shm_buffer_hires_name)

    if platform.system() == "Windows":
        logger.info("force VideoCapture to DSHOW backend on windows (MSMF is buggy and crashes app)")
        _video = cv2.VideoCapture(_config.backends.cv2_device_index, cv2.CAP_DSHOW)
    else:
        _video = cv2.VideoCapture(_config.backends.cv2_device_index)

    # activate preview mode on init
    _video_set_check(_video, cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    _video_set_check(_video, cv2.CAP_PROP_FPS, 30.0)
    _video_set_check(_video, cv2.CAP_PROP_FRAME_WIDTH, _config.common.CAPTURE_CAM_RESOLUTION_WIDTH)
    _video_set_check(
        _video,
        cv2.CAP_PROP_FRAME_HEIGHT,
        _config.common.CAPTURE_CAM_RESOLUTION_HEIGHT,
    )

    if not _video.isOpened():
        raise OSError(f"cannot open camera index {_config.backends.cv2_device_index}")

    if not _video.read()[0]:
        raise OSError(f"cannot read camera index {_config.backends.cv2_device_index}")

    logger.info(f"webcam cv2 using backend {_video.getBackendName()}")
    logger.info(
        f"webcam resolution: {int(_video.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
        f"{int(_video.get(cv2.CAP_PROP_FRAME_HEIGHT))}"
    )

    # read first five frames and send to void
    for _ in range(5):
        _, _ = _video.read()

    while not _event_proc_shutdown.is_set():
        ret, array = _video.read()
        # ret=True successful read, otherwise False?
        if not ret:
            raise OSError("error reading camera frame")

        # apply flip image to stream only:
        if _config.common.CAMERA_TRANSFORM_HFLIP:
            array = cv2.flip(array, 1)
        if _config.common.CAMERA_TRANSFORM_VFLIP:
            array = cv2.flip(array, 0)

        if _event_hq_capture.is_set():
            _event_hq_capture.clear()

            # one time hq still

            # array = cv2.fastNlMeansDenoisingColored(array, None, 2, 2, 3, 9)
            # above command takes too long time -> timeout on wait commands
            # HD frame needs like 2sec, not suitable for realtime processing

            # convert frame to jpeg buffer
            jpeg_buffer = turbojpeg.encode(array, quality=_config.common.HIRES_STILL_QUALITY)
            # put jpeg on queue until full. If full this function blocks until queue empty
            with _img_buffer_hires_lock:
                compile_buffer(shm_hires, jpeg_buffer)

            with _condition_img_buffer_hires_ready:
                # wait to be notified
                _condition_img_buffer_hires_ready.notify_all()
        else:
            # preview livestream
            jpeg_buffer = turbojpeg.encode(array, quality=_config.common.LIVEPREVIEW_QUALITY)
            # put jpeg on queue until full. If full this function blocks until queue empty
            with _img_buffer_lores_lock:
                compile_buffer(shm_lores, jpeg_buffer)

            with _condition_img_buffer_lores_ready:
                # wait to be notified
                _condition_img_buffer_lores_ready.notify_all()

    # release camera on process shutdown
    _video.release()


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
