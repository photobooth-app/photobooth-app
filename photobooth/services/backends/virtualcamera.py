"""
Virtual Camera backend for testing.
"""

import logging
import mmap
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition

from ...utils.stoppablethread import StoppableThread
from ..config.groups.backends import GroupBackendVirtualcamera
from .abstractbackend import AbstractBackend, GeneralBytesResult

FPS_TARGET = 25

logger = logging.getLogger(__name__)


class VirtualCameraBackend(AbstractBackend):
    def __init__(self, config: GroupBackendVirtualcamera):
        self._config: GroupBackendVirtualcamera = config
        super().__init__(failing_wait_for_lores_image_is_error=True)

        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=None, condition=Condition())
        self._worker_thread: StoppableThread = None

    def start(self):
        super().start()

        self._worker_thread = StoppableThread(name="virtualcamera_worker_thread", target=self._worker_fun, daemon=True)
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
        worker_alive = self._worker_thread and self._worker_thread.is_alive()

        return super_alive and worker_alive

    def _device_available(self) -> bool:
        """virtual camera to be available always"""
        return True

    def _wait_for_multicam_files(self) -> list[Path]:
        files: list[Path] = []

        for _ in range(self._config.emulate_multicam_capture_devices):
            files.append(self._wait_for_still_file())

        return files

    def _wait_for_still_file(self) -> Path:
        """for other threads to receive a hq JPEG image"""

        time.sleep(self._config.emulate_camera_delay_still_capture)

        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix="virtualcamera_") as f:
            f.write(self._wait_for_lores_image())

            return Path(f.name)

    def _wait_for_lores_image(self):
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

    #
    # INTERNAL IMAGE GENERATOR
    #

    def _worker_fun(self):
        logger.info("virtualcamera thread function starts")

        jpeg_chunks = []  # offset, len --> seek(offset), read(len)
        last_chunk = 0
        last_offset = 0

        with open(Path(__file__).parent.joinpath("assets", "backend_virtualcamera", "video", "demovideo.mjpg").resolve(), "rb") as stream_file_obj:
            with mmap.mmap(stream_file_obj.fileno(), length=0, access=mmap.ACCESS_READ) as stream_mmap_obj:
                # preprocess video, get chunks of jpeg to slice out of mjpg file (which is just jpg's concatenated)
                bytes = b""
                for chunk in iter(lambda: stream_mmap_obj.read(4096), b""):
                    bytes += chunk
                    a = bytes.find(b"\xff\xd8")  # jpeg start code
                    b = bytes.find(b"\xff\xd9")  # jpeg end code
                    if a != -1 and b != -1:
                        jpeg_chunks.append((last_offset + a, b + 2))  # offset,len
                        bytes = bytes[b + 2 :]  # reset bytes var to start at next jpg
                        last_offset += b + 2

                logger.info(f"found {len(jpeg_chunks)} images in virtualcamera video")

                self._device_set_is_ready_to_deliver()

                last_time_frame = time.time()
                while not self._worker_thread.stopped():  # repeat until stopped
                    now_time = time.time()
                    if (now_time - last_time_frame) <= (1.0 / self._config.framerate):
                        # limit max framerate to every ~5ms
                        time.sleep(0.005)
                        continue
                    last_time_frame = now_time

                    if last_chunk >= len(jpeg_chunks):
                        last_chunk = 0  # start over at the beginning
                    stream_mmap_obj.seek(jpeg_chunks[last_chunk][0])
                    jpeg_bytes = stream_mmap_obj.read(jpeg_chunks[last_chunk][1])
                    last_chunk += 1

                    # success
                    with self._lores_data.condition:
                        self._lores_data.data = jpeg_bytes
                        self._lores_data.condition.notify_all()

                    self._frame_tick()

        self._device_set_is_ready_to_deliver(False)
        logger.info("virtualcamera thread finished")
