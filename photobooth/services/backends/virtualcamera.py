"""
Virtual Camera backend for testing.
"""

import dataclasses
import logging
import mmap
import time
from pathlib import Path
from threading import Condition

from ...utils.stoppablethread import StoppableThread
from ..config.groups.backends import GroupBackendVirtualcamera
from .abstractbackend import AbstractBackend

FPS_TARGET = 25

logger = logging.getLogger(__name__)


class VirtualCameraBackend(AbstractBackend):
    """Virtual camera backend to test photobooth"""

    @dataclasses.dataclass
    class VirtualcameraDataBytes:
        """
        bundle data bytes and it's condition.
        1) save some instance attributes and
        2) bundle as it makes sense
        """

        # jpeg data as bytes
        data: bytes = None
        # condition when frame is avail
        condition: Condition = None

    def __init__(self, config: GroupBackendVirtualcamera):
        self._config: GroupBackendVirtualcamera = config
        super().__init__()
        self._failing_wait_for_lores_image_is_error = True  # missing lores images is automatically considered as error

        self._lores_data: __class__.VirtualcameraDataBytes = __class__.VirtualcameraDataBytes(
            data=None,
            condition=Condition(),
        )

        # worker threads
        self._worker_thread: StoppableThread = None

    def _device_start(self):
        """To start the image backend"""
        # ensure shutdown event is cleared (needed for restart during testing)

        self._worker_thread = StoppableThread(name="virtualcamera_worker_thread", target=self._worker_fun, daemon=True)
        self._worker_thread.start()

        # wait until threads are up and deliver images actually. raises exceptions if fails after several retries
        self._block_until_delivers_lores_images()

        logger.debug(f"{self.__module__} started")

    def _device_stop(self):
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.stop()
            self._worker_thread.join()

        logger.debug(f"{self.__module__} stopped")

    def _device_available(self) -> bool:
        """virtual camera to be available always"""
        return True

    def _wait_for_hq_image(self):
        """for other threads to receive a hq JPEG image"""

        time.sleep(self._config.emulate_camera_delay_still_capture)

        return self._wait_for_lores_image()

    #
    # INTERNAL FUNCTIONS
    #

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

        last_time_frame = time.time_ns()

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

                while not self._worker_thread.stopped():  # repeat until stopped
                    now_time = time.time_ns()
                    if (now_time - last_time_frame) / 1000**3 <= (1 / FPS_TARGET):
                        # limit max framerate to every ~2ms
                        time.sleep(0.002)
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

        logger.info("virtualcamera thread finished")
