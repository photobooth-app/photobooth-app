"""
Virtual Camera backend for testing.
"""

import logging
import mmap
import time
from itertools import cycle
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition

from ...utils.stoppablethread import StoppableThread
from ..config.groups.backends import GroupBackendVirtualcamera
from .abstractbackend import AbstractBackend, GeneralBytesResult

logger = logging.getLogger(__name__)


class CyclicImageSource:
    def __init__(self):
        self.jpeg_chunks_iter = cycle(self.__preprocess__source())  # cycle iterable to offset, len --> seek(offset), read(len)

    def __preprocess__source(self):
        jpeg_chunks: list[tuple[int, int]] = []  # offset, len --> seek(offset), read(len)
        last_offset = 0

        with open(Path(__file__).parent.joinpath("assets", "backend_virtualcamera", "video", "demovideo.mjpg").resolve(), "rb") as stream_file_obj:
            # preprocess video, get chunks of jpeg to slice out of mjpg file (which is just jpg's concatenated)
            concat_chunk = b""
            for chunk in iter(lambda: stream_file_obj.read(4096), b""):
                concat_chunk += chunk
                a = concat_chunk.find(b"\xff\xd8")  # jpeg start code
                b = concat_chunk.find(b"\xff\xd9")  # jpeg end code
                if a != -1 and b != -1:
                    jpeg_chunks.append((last_offset + a, b + 2))  # offset,len
                    concat_chunk = concat_chunk[b + 2 :]  # reset bytes var to start at next jpg
                    last_offset += b + 2

            logger.info(f"found {len(jpeg_chunks)} images in virtualcamera video")

        return jpeg_chunks

    def images(self):
        with open(Path(__file__).parent.joinpath("assets", "backend_virtualcamera", "video", "demovideo.mjpg").resolve(), "rb") as stream_file_obj:
            with mmap.mmap(stream_file_obj.fileno(), length=0, access=mmap.ACCESS_READ) as stream_mmap_obj:
                while True:
                    slice_chunk = next(self.jpeg_chunks_iter)
                    stream_mmap_obj.seek(slice_chunk[0])

                    yield stream_mmap_obj.read(slice_chunk[1])


class VirtualCameraBackend(AbstractBackend):
    def __init__(self, config: GroupBackendVirtualcamera):
        # print(VirtualCameraBackend.__mro__)
        self._config: GroupBackendVirtualcamera = config
        super().__init__(orientation=config.orientation)

        self._images_iterator = CyclicImageSource().images()
        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=b"", condition=Condition())
        self._worker_thread: StoppableThread | None = None

    def start(self):
        super().start()

        logger.debug(f"{self.__module__} started")

    def stop(self):
        super().stop()

        logger.debug(f"{self.__module__} stopped")

    def setup_resource(self):
        logger.info("Connecting to resource...")

    def teardown_resource(self):
        logger.info("Disconnecting from resource...")

    def run_service(self):
        logger.info("Running service logic...")

        # raise RuntimeError("Simulated crash")

        last_time_frame = time.time()
        while not self._stop_event.is_set():
            now_time = time.time()
            if (now_time - last_time_frame) <= (1.0 / self._config.framerate):
                # limit max framerate to every ~5ms
                time.sleep(0.005)
                continue
            last_time_frame = now_time

            # success
            with self._lores_data.condition:
                self._lores_data.data = next(self._images_iterator)
                self._lores_data.condition.notify_all()

            self._frame_tick()

        logger.info("virtualcamera thread finished")

    def _wait_for_multicam_files(self) -> list[Path]:
        files: list[Path] = []

        for _ in range(self._config.emulate_multicam_capture_devices):
            files.append(self._wait_for_still_file())

        return files

    def _wait_for_still_file(self) -> Path:
        """for other threads to receive a hq JPEG image"""

        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix="virtualcamera_", suffix=".jpg") as f:
            if self._config.emulate_hires_static_still:
                with open(Path(__file__).parent.joinpath("assets", "backend_virtualcamera", "video", "hires.jpg").resolve(), "rb") as f_hires:
                    f.write(f_hires.read())
            else:
                f.write(next(self._images_iterator))

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
