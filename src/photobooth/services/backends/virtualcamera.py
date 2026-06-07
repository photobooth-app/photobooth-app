"""
Virtual Camera backend for testing.
"""

import logging
import mmap
import time
from itertools import cycle
from pathlib import Path
from tempfile import NamedTemporaryFile

from ...utils.helper import filename_str_time
from ...utils.stoppablethread import StoppableThread
from ..config.groups.cameras import GroupCameraVirtual
from .abstractbackend import AbstractBackend, MulticamRequest, StillRequest

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
    def __init__(self, config: GroupCameraVirtual):
        # print(VirtualCameraBackend.__mro__)
        self._config: GroupCameraVirtual = config
        super().__init__(
            orientation=config.orientation,
            num_subdevices=self._config.emulate_multicam_capture_devices,
            idle_timeout=self._config.camera_standby_when_inactive_time if self._config.camera_standby_when_inactive else None,
        )

        self._images_iterator = CyclicImageSource().images()
        # self._enable_producer: bool = False
        self._worker_thread: StoppableThread | None = None

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def setup_resource(self):
        pass

    def teardown_resource(self):
        pass

    def run_service(self):

        while not self._stop_event.is_set():
            with self._hires_lock:
                req = self._hires_queue.popleft() if self._hires_queue else None

            if req:
                self._mode_machine.process_switchmode("still")

                if isinstance(req, StillRequest):
                    file = self._produce_still(req.subdevice_index)
                    with req.condition:
                        req.result_file = file
                        req.condition.notify_all()
                elif isinstance(req, MulticamRequest):
                    files = self._produce_multicam()
                    with req.condition:
                        req.result_files = files
                        req.condition.notify_all()
                else:
                    logger.warning(f"this backend does not support {type(req)} requests")
                    continue

            self._mode_machine.process_switchmode()

            if self._mode_machine.active_mode == "standby":
                time.sleep(0.1)
                continue

            self._mode_machine.process_switchmode("video")

            self._framerate.wait_until_fps(self._config.framerate)

            # "produce" next lores-frame
            frame = next(self._images_iterator)
            self._frame_tick()

            for dev_idx in range(self._config.emulate_multicam_capture_devices):
                with self._lores_data[dev_idx].condition:
                    self._lores_data[dev_idx].data = frame
                    self._lores_data[dev_idx].condition.notify_all()

        logger.debug("virtualcamera thread finished")

    def _produce_multicam(self) -> list[Path]:
        files: list[Path] = []

        for i in range(self._config.emulate_multicam_capture_devices):
            files.append(self._produce_still(i))

        return files

    def _produce_still(self, index_subdevice: int = 0) -> Path:
        """for other threads to receive a hq JPEG image"""

        with NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir="tmp",
            prefix=f"{filename_str_time()}_virtualcamera_subdevice{index_subdevice}_",
            suffix=".jpg",
        ) as f:
            if self._config.emulate_hires_static_still:
                with open(Path(__file__).parent.joinpath("assets", "backend_virtualcamera", "video", "hires.jpg").resolve(), "rb") as f_hires:
                    f.write(f_hires.read())
            else:
                f.write(next(self._images_iterator))

            return Path(f.name)

    def _capture_lores(self, index_subdevice: int = 0) -> bytes:
        with self._lores_data[index_subdevice].condition:
            if not self._lores_data[index_subdevice].condition.wait(timeout=0.5):
                raise TimeoutError("timeout receiving frames")

            return self._lores_data[index_subdevice].data

    def _handle_switchmode_video_mode(self):
        super()._handle_switchmode_video_mode()

    def _handle_switchmode_still_mode(self):
        super()._handle_switchmode_still_mode()

    def _handle_switchmode_standby(self):
        super()._handle_switchmode_standby()
