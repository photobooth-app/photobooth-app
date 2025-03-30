"""
pyav webcam implementation backend
"""

import logging
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition, Event
from typing import Literal

import av

from ...utils.stoppablethread import StoppableThread
from ..config.groups.backends import GroupBackendPyav
from .abstractbackend import AbstractBackend, GeneralBytesResult, GeneralFileResult

logger = logging.getLogger(__name__)

input_ffmpeg_device = "dshow" if sys.platform == "win32" else None


class WebcamPyavBackend(AbstractBackend):
    def __init__(self, config: GroupBackendPyav):
        self._config: GroupBackendPyav = config
        super().__init__(orientation=config.orientation)

        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=b"", condition=Condition())
        self._hires_data = GeneralFileResult(filepath=None, request=Event(), condition=Condition())
        self._worker_thread: StoppableThread | None = None

    def start(self):
        super().start()

        self._worker_thread = StoppableThread(name="webcampyav_worker_thread", target=self._worker_fun, daemon=True)
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
        try:
            with av.open(f"video={self._config.device_name}", format=input_ffmpeg_device, options=self._get_options("lores")):
                pass
            return True
        except Exception:
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
        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix="webcampyav_lores_", suffix=".jpg") as f:
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

    def _get_options(self, mode: Literal["hires", "lores"]):
        logger.info(f"get options, mode {mode}")

        if mode == "hires":
            video_size = f"{self._config.HIRES_CAM_RESOLUTION_WIDTH}x{self._config.HIRES_CAM_RESOLUTION_HEIGHT}"
        else:
            video_size = f"{self._config.CAM_RESOLUTION_WIDTH}x{self._config.CAM_RESOLUTION_HEIGHT}"

        return {
            "video_size": video_size,
            # "framerate": "30",
            "input_format": "mjpeg",
        }

    def _worker_fun(self):
        logger.info("_worker_fun starts")
        logger.info(f"trying to open camera index={self._config.device_name=}")

        assert self._worker_thread

        self._device_set_is_ready_to_deliver()

        while not self._worker_thread.stopped():
            if self._hires_data.request.is_set():
                # hires

                # only capture one pic and return to lores streaming afterwards
                self._hires_data.request.clear()

                with av.open(f"video={self._config.device_name}", format=input_ffmpeg_device, options=self._get_options("hires")) as input_device:
                    frame_nb = 0
                    for packet in input_device.demux():  # forever
                        if packet.stream.type == "video":
                            # throw away the first x frames to allow the camera to settle again.
                            if frame_nb <= self._config.flush_number_frames_after_switch:
                                frame_nb += 1
                                continue

                            if self._config.flush_number_frames_after_switch:
                                logger.info("skipped {self._config.flush_number_frames_after_switch} frames before capture high resolution image")

                            with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix="webcampyav_hires_", suffix=".jpg") as f:
                                f.write(bytes(packet))

                            self._hires_data.filepath = Path(f.name)
                            with self._hires_data.condition:
                                self._hires_data.condition.notify_all()

                            # grab just one frame...
                            break

            else:
                # lores
                with av.open(f"video={self._config.device_name}", format=input_ffmpeg_device, options=self._get_options("lores")) as input_device:
                    for packet in input_device.demux():  # forever
                        if packet.stream.type == "video":
                            with self._lores_data.condition:
                                self._lores_data.data = bytes(packet)
                                self._lores_data.condition.notify_all()

                            self._frame_tick()

                        # leave lores in favor to hires still capture for 1 frame.
                        if self._hires_data.request.is_set():
                            break

                        # abort streaming on shutdown so process can join and close
                        if self._worker_thread.stopped():
                            break

        self._device_set_is_ready_to_deliver(False)
        logger.info("pyav_img_aquisition finished, exit")


def available_camera_names() -> list[str]:
    raise NotImplementedError("currently no listing of devices supported.")
