"""
v4l webcam implementation backend
"""

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition, Event
from typing import Literal

from ...utils.stoppablethread import StoppableThread
from ..config.groups.backends import GroupBackendV4l2
from .abstractbackend import AbstractBackend, GeneralBytesResult, GeneralFileResult

try:
    import linuxpy.video.device as linuxpy_video_device  # type: ignore
except ImportError:
    linuxpy_video_device = None


logger = logging.getLogger(__name__)


class WebcamV4lBackend(AbstractBackend):
    def __init__(self, config: GroupBackendV4l2):
        self._config: GroupBackendV4l2 = config
        super().__init__(orientation=config.orientation)

        if linuxpy_video_device is None:
            raise ModuleNotFoundError("Backend is not available - either wrong platform or not installed!")

        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=b"", condition=Condition())
        self._hires_data = GeneralFileResult(filepath=None, request=Event(), condition=Condition())
        self._worker_thread: StoppableThread | None = None

    def start(self):
        super().start()

        self._worker_thread = StoppableThread(name="webcamv4l_worker_thread", target=self._worker_fun, daemon=True)
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
        if self._config.device_index in available_camera_indexes():
            return True
        else:
            return False

    def _wait_for_multicam_files(self) -> list[Path]:
        raise NotImplementedError("backend does not support multicam files")

    def _wait_for_still_file(self) -> Path:
        """
        for other threads to receive a hq JPEG image
        mode switches are handled internally automatically, no separate trigger necessary
        this function blocks until frame is received
        raise TimeoutError if no frame was received
        """

        if self._config.switch_to_high_resolution_for_stills:
            return self._wait_for_still_file_switch_hires()
        else:
            return self._wait_for_still_file_noswitch_lores()

    def _wait_for_still_file_switch_hires(self) -> Path:
        assert self._hires_data

        with self._hires_data.condition:
            self._hires_data.request.set()

            if not self._hires_data.condition.wait(timeout=4):
                # wait returns true if timeout expired
                raise TimeoutError("timeout receiving frames")

            self._hires_data.request.clear()
            assert self._hires_data.filepath

            return self._hires_data.filepath

    def _wait_for_still_file_noswitch_lores(self) -> Path:
        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix="webcamv4l2_lores_", suffix=".jpg") as f:
            f.write(self._wait_for_lores_image())
            return Path(f.name)

    def _wait_for_lores_image(self) -> bytes:
        """for other threads to receive a lores JPEG image"""

        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=0.5):
                raise TimeoutError("timeout receiving frames")

            return self._lores_data.data

    def _on_configure_optimized_for_idle(self):
        pass

    def _on_configure_optimized_for_hq_preview(self):
        pass

    def _on_configure_optimized_for_hq_capture(self):
        pass

    def _switch_mode(self, capture, mode: Literal["hires", "lores"]):
        logger.info(f"switch_mode to {mode} requested")

        if mode == "hires":
            width, height = self._config.HIRES_CAM_RESOLUTION_WIDTH, self._config.HIRES_CAM_RESOLUTION_HEIGHT
        else:
            width, height = self._config.CAM_RESOLUTION_WIDTH, self._config.CAM_RESOLUTION_HEIGHT

        try:
            capture.set_format(width, height, "MJPG")
            fmt = capture.get_format()
            logger.info(f"cam resolution set to {fmt.width}x{fmt.height} for {mode}-mode using format {fmt.pixel_format.name}")
        except Exception as exc:
            logger.error(f"error switching mode due to {exc}")

    def _worker_fun(self):
        logger.info("_worker_fun starts")
        logger.info(f"trying to open camera index={self._config.device_index=}")

        assert linuxpy_video_device
        assert self._worker_thread

        with linuxpy_video_device.Device.from_id(self._config.device_index) as device:
            logger.info(f"webcam device index: {self._config.device_index}")
            logger.info(f"webcam: {device.info.card if device.info else 'unknown'}")

            capture = linuxpy_video_device.VideoCapture(device)

            try:
                capture.set_fps(25)
            except OSError as exc:
                logger.warning(f"cannot set_fps due to error: {exc}")
                # continue even if error occured, camera might not support fps setting...

            self._switch_mode(capture, "lores")

            while not self._worker_thread.stopped():
                if self._hires_data.request.is_set():
                    # only capture one pic and return to lores streaming afterwards
                    self._hires_data.request.clear()

                    self._switch_mode(capture, "hires")

                    # capture hq picture
                    for frame in device:
                        # throw away the first x frames to allow the camera to settle again.
                        if frame.frame_nb <= self._config.flush_number_frames_after_switch:
                            continue

                        if self._config.flush_number_frames_after_switch:
                            logger.info("skipped {self._config.flush_number_frames_after_switch} frames before capture high resolution image")

                        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix="webcamv4l2_hires_", suffix=".jpg") as f:
                            f.write(bytes(frame))

                        self._hires_data.filepath = Path(f.name)

                        # grab just one frame...
                        break

                    with self._hires_data.condition:
                        self._hires_data.condition.notify_all()
                else:
                    self._switch_mode(capture, "lores")

                    for frame in device:  # forever
                        # do it here, because opening device for for loop iteration takes also some time that is abstracted by the lib
                        if not self.is_ready_to_deliver.is_set():
                            # set only once.
                            self._device_set_is_ready_to_deliver()

                        with self._lores_data.condition:
                            self._lores_data.data = bytes(frame)
                            self._lores_data.condition.notify_all()

                        self._frame_tick()

                        # leave lores in favor to hires still capture for 1 frame.
                        if self._hires_data.request.is_set():
                            break

                        # abort streaming on shutdown so process can join and close
                        if self._worker_thread.stopped():
                            break

        self._device_set_is_ready_to_deliver(False)
        logger.info("v4l_img_aquisition finished, exit")


def available_camera_indexes() -> list[int]:
    if linuxpy_video_device is None:
        raise ModuleNotFoundError("Backend is not available - either wrong platform or not installed!")

    mjpeg_stream_devices: list[int] = []

    devices_list = list(linuxpy_video_device.iter_video_capture_devices())

    for device_list in devices_list:
        with linuxpy_video_device.Device(device_list.filename) as device:
            assert device.info
            if any(device_format.pixel_format == linuxpy_video_device.PixelFormat.MJPEG for device_format in device.info.formats):
                if device.index is not None:
                    mjpeg_stream_devices.append(device.index)

    return mjpeg_stream_devices
