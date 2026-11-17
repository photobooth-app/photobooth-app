import hashlib
import logging
import time
from collections.abc import Generator
from itertools import cycle
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import av
import av.codec
from av.video.reformatter import Interpolation, VideoReformatter
from simplejpeg import encode_jpeg_yuv_planes

from ...utils.helper import filename_str_time
from ...utils.metrics_timer import MetricsTimer
from ..config.groups.cameras import GroupCameraVirtual
from .abstractbackend import AbstractBackend, MulticamRequest, StillRequest

logger = logging.getLogger(__name__)


class FolderImageSource:
    """
    Read all JPEGs from a folder, mmap them once, and cycle endlessly.
    """

    def __init__(self, folder: Path):
        self.folder = folder

        self.jpeg_paths = sorted(folder.glob("*.jpg"), key=lambda p: p.stem)
        if not self.jpeg_paths:
            raise RuntimeError(f"No JPEGs found in {folder}")

        self._frames = [p.read_bytes() for p in self.jpeg_paths]
        self.iter = cycle(self._frames)

    def close(self):
        self._frames.clear()


class VirtualCameraBackend(AbstractBackend):
    asset_file = Path(__file__).parent.joinpath("assets", "backend_virtualcamera", "video", "demovideo.mp4").resolve()
    asset_nominal_fps = 25
    asset_extracted_folder = Path.home() / ".photobooth-data" / "virtualcamera"

    def __init__(self, config: GroupCameraVirtual):
        # print(VirtualCameraBackend.__mro__)
        self._config: GroupCameraVirtual = config
        super().__init__(
            orientation=config.orientation,
            num_subdevices=self._config.emulate_multicam_capture_devices,
            idle_timeout=self._config.camera_standby_when_inactive_time if self._config.camera_standby_when_inactive else None,
        )

        self._folder_image_source: FolderImageSource | None = None
        self._images_iter: Generator[bytes, Any, None] | None = None

    def start(self):
        super().start()

    def stop(self):

        super().stop()

    def images(self):
        assert self._folder_image_source
        source_fps = self.asset_nominal_fps
        target_fps = self._config.framerate

        ratio = source_fps / target_fps  # / is float div
        accu = 0.0

        while not self._stop_event.is_set():
            frame = next(self._folder_image_source.iter)
            accu += 1.0
            if accu >= ratio:
                accu -= ratio

                self._frame_tick()
                yield frame

                time.sleep(1.0 / target_fps)

    def setup_resource(self):
        with MetricsTimer(f"ensure unpacked demo video exists at {self.asset_extracted_folder}"):
            self.ensure_extracted(self.asset_file, self.asset_extracted_folder)

        self._folder_image_source = FolderImageSource(self.asset_extracted_folder)
        self._images_iter = self.images()

    def teardown_resource(self):
        if self._images_iter:
            self._images_iter.close()

        if self._folder_image_source:
            self._folder_image_source.close()

    @staticmethod
    def file_hash(path: Path) -> str:
        h = hashlib.sha256()
        h.update(path.read_bytes())

        return h.hexdigest()

    @classmethod
    def ensure_extracted(cls, asset_file: Path, asset_extracted_folder: Path):
        done_file = asset_extracted_folder / "extraction.done"

        # Compute hash of input video to detect changes
        current_hash = cls.file_hash(asset_file)

        # Case 1: No sentinel → extract
        if not done_file.exists():
            cls.extract_all(asset_file, asset_extracted_folder, current_hash)
            return

        # Case 2: Sentinel exists → verify hash
        try:
            stored_hash = done_file.read_text().strip()
        except OSError:
            stored_hash = ""
        if stored_hash != current_hash:
            # asset video changed → rebuild
            for f in asset_extracted_folder.glob("*.jpg"):
                f.unlink()

            cls.extract_all(asset_file, asset_extracted_folder, current_hash)
            return

        # Case 3: Sentinel exists but directory empty → rebuild
        if not any(asset_extracted_folder.glob("*.jpg")):
            cls.extract_all(asset_file, asset_extracted_folder, current_hash)
            return

    @classmethod
    def extract_all(cls, asset_file: Path, folder_out: Path, asset_hash: str):
        folder_out.mkdir(parents=True, exist_ok=True)

        cls.extract_jpegs_from_video(asset_file, folder_out)

        # Write sentinel atomically
        done_file = folder_out / "extraction.tmp"
        done_file.write_text(asset_hash)
        done_file.rename(folder_out / "extraction.done")

    @classmethod
    def extract_jpegs_from_video(cls, file_in: Path, folder_out: Path):

        reformatter = VideoReformatter()

        with av.open(file_in, mode="r") as input_device:
            input_stream = input_device.streams.video[0]
            input_stream.thread_type = av.codec.context.ThreadType.AUTO
            input_stream.thread_count = 0

            rW = input_stream.width
            rH = input_stream.height

            for i, frame in enumerate(input_device.decode(input_stream)):
                resized_frame = reformatter.reformat(frame, width=rW, height=rH, interpolation=Interpolation.BILINEAR, format="yuv420p").to_ndarray()

                with open(folder_out / f"{i:04d}.jpg", "wb") as fout:
                    fout.write(
                        encode_jpeg_yuv_planes(
                            Y=resized_frame[:rH],
                            U=resized_frame.reshape(rH * 3, rW // 2)[rH * 2 : rH * 2 + rH // 2],
                            V=resized_frame.reshape(rH * 3, rW // 2)[rH * 2 + rH // 2 :],
                            quality=85,
                            fastdct=True,
                        )
                    )

    def run_service(self):
        assert self._images_iter
        while not self._stop_event.is_set():
            with self._hires_lock:
                req = self._hires_queue.popleft() if self._hires_queue else None

            if req:
                with self._mode_machine.ext_mode_switch_lock:
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

            # "produce" next lores-frame
            try:
                frame = next(self._images_iter)
            except StopIteration:
                return

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

        assert self._images_iter

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
                try:
                    frame = next(self._images_iter)
                    f.write(frame)
                except StopIteration as exc:
                    raise RuntimeError("shutdown app during still capture") from exc

            return Path(f.name)

    def _capture_lores(self, index_subdevice: int = 0) -> bytes:
        with self._lores_data[index_subdevice].condition:
            if not self._lores_data[index_subdevice].condition.wait(timeout=0.5):
                raise TimeoutError("timeout receiving frames")

            return self._lores_data[index_subdevice].data

    def _handle_switchmode_init(self):
        pass

    def _handle_switchmode_video_mode(self):
        pass

    def _handle_switchmode_still_mode(self):
        pass

    def _handle_switchmode_standby(self):
        pass
