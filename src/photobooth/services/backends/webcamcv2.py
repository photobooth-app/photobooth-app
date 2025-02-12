"""
backend opencv2 for webcameras
"""

import logging
import platform
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition

import cv2

from ...utils.stoppablethread import StoppableThread
from ..config.groups.backends import GroupBackendOpenCv2
from .abstractbackend import AbstractBackend, GeneralBytesResult

logger = logging.getLogger(__name__)


class WebcamCv2Backend(AbstractBackend):
    def __init__(self, config: GroupBackendOpenCv2):
        self._config: GroupBackendOpenCv2 = config
        super().__init__(orientation=config.orientation)

        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=b"", condition=Condition())
        self._worker_thread: StoppableThread | None = None

    def start(self):
        super().start()

        self._worker_thread = StoppableThread(name="webcamcv2_worker_thread", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.stop()
            self._worker_thread.join()

        logger.debug(f"{self.__module__} stopped")

    def _device_alive(self) -> bool:
        super_alive = super()._device_alive()
        worker_alive = bool(self._worker_thread and self._worker_thread.is_alive())

        return super_alive and worker_alive

    def _device_available(self):
        """
        For cv2 we check to open device is possible
        """
        device = cv2.VideoCapture(self._config.device_index)
        ret, array = device.read()  # ret True if connected properly, otherwise False
        if ret:
            device.release()

        return ret

    def _wait_for_multicam_files(self) -> list[Path]:
        raise NotImplementedError("backend does not support multicam files")

    def _wait_for_still_file(self) -> Path:
        """for other threads to receive a hq JPEG image"""
        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix="webcamcv2_", suffix=".jpg") as f:
            f.write(self._wait_for_lores_image())
            return Path(f.name)

    def _wait_for_lores_image(self):
        """for other threads to receive a lores JPEG image"""

        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=0.75):
                raise TimeoutError("timeout receiving frames")

            return self._lores_data.data

    def _on_configure_optimized_for_idle(self):
        pass

    def _on_configure_optimized_for_hq_preview(self):
        pass

    def _on_configure_optimized_for_hq_capture(self):
        pass

    #
    # INTERNAL IMAGE GENERATOR
    #

    def _worker_fun(self):
        assert self._worker_thread
        logger.info("_worker_fun starts")

        if platform.system() == "Windows":
            logger.info("force VideoCapture to DSHOW backend on windows (MSMF is buggy and crashes app)")
            _video = cv2.VideoCapture(self._config.device_index, cv2.CAP_DSHOW)
        else:
            _video = cv2.VideoCapture(self._config.device_index)

        # activate preview mode on init
        _video_set_check(_video, cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*"MJPG"))
        _video_set_check(_video, cv2.CAP_PROP_FPS, 25.0)
        _video_set_check(_video, cv2.CAP_PROP_FRAME_WIDTH, self._config.CAM_RESOLUTION_WIDTH)
        _video_set_check(_video, cv2.CAP_PROP_FRAME_HEIGHT, self._config.CAM_RESOLUTION_HEIGHT)

        if not _video.isOpened():
            raise OSError(f"cannot open camera index {self._config.device_index}")

        if not _video.read()[0]:
            raise OSError(f"cannot read camera index {self._config.device_index}")

        logger.info(f"webcam cv2 using backend {_video.getBackendName()}")
        logger.info(f"webcam resolution: {int(_video.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(_video.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

        # read first five frames and send to void
        for _ in range(5):
            _, _ = _video.read()

        self._device_set_is_ready_to_deliver()

        last_time_frame = time.time()
        while not self._worker_thread.stopped():  # repeat until stopped
            now_time = time.time()
            if (now_time - last_time_frame) <= (1.0 / self._config.framerate):
                # limit max framerate to every ~5ms
                time.sleep(0.005)
                continue

            last_time_frame = now_time
            # print(time.monotonic())
            ret, array = _video.read()
            # ret=True successful read, otherwise False?
            if not ret:
                raise OSError("error reading camera frame")

            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
            result, jpeg_buffer = cv2.imencode(".jpg", array, encode_param)

            with self._lores_data.condition:
                self._lores_data.data = jpeg_buffer.tobytes()
                self._lores_data.condition.notify_all()

            self._frame_tick()

        # release camera on process shutdown
        _video.release()

        self._device_set_is_ready_to_deliver(False)
        logger.info("worker_fun finished, exit")


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
