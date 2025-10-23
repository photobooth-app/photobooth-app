import logging
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Condition

import pynng

from ...utils.helper import filename_str_time
from ..config.groups.cameras import GroupCameraWigglecam
from .abstractbackend import AbstractBackend, GeneralBytesResult

logger = logging.getLogger(__name__)


@dataclass
class ImageMessage:
    """This is packaged in the wigglecam nodes and needs to decode here:
    TODO: Maybe in future reuse the definition from the wigglecam module, once everything stabilizes.
    For now keep it as is, since this one is the only item depends on wigglecam as import.

    """

    device_id: int
    jpg_bytes: bytes
    job_id: uuid.UUID | None = None

    _header_fmt = "iI16s"  # device_id, jpg_len, uuid (16 Bytes)

    @classmethod
    def from_bytes(cls, data: bytes) -> "ImageMessage":
        header_size = struct.calcsize(cls._header_fmt)
        device_id, jpg_len, uuid_bytes = struct.unpack(cls._header_fmt, data[:header_size])
        jpg_bytes = data[header_size : header_size + jpg_len]
        job_id = None if uuid_bytes == b"\x00" * 16 else uuid.UUID(bytes=uuid_bytes)
        return cls(device_id, jpg_bytes, job_id)


class WigglecamBackend(AbstractBackend):
    def __init__(self, config: GroupCameraWigglecam):
        super().__init__()
        self._config = config

        self._lores_data: GeneralBytesResult = GeneralBytesResult(data=b"", condition=Condition())
        self._pub_trigger: pynng.Pub0 | None = None
        self._sub_lores: pynng.Sub0 | None = None
        self._sub_hires: pynng.Sub0 | None = None

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def setup_resource(self):
        max_index = max(self._config.index_cam_stills, self._config.index_cam_video)
        if max_index > len(self._config.devices) - 1:
            raise RuntimeError(f"configuration error: index out of range! {max_index=} whereas max_index allowed={len(self._config.devices) - 1}")

        # host also subscribes to the hires replies
        self._pub_trigger = pynng.Pub0()
        for node in self._config.devices:
            self._pub_trigger.dial(f"tcp://{node.address}:{node.base_port + 0}", block=False)

        # Listen for lores streams
        self._sub_lores = pynng.Sub0()
        self._sub_lores.subscribe(b"")
        self._sub_lores.recv_timeout = 1000
        for node in self._config.devices:
            self._sub_lores.dial(f"tcp://{node.address}:{node.base_port + 1}", block=False)

        # Setup Sub for hires
        self._sub_hires = pynng.Sub0()
        self._sub_hires.subscribe(b"")
        self._sub_hires.recv_timeout = 1000
        for node in self._config.devices:
            self._sub_hires.dial(f"tcp://{node.address}:{node.base_port + 2}", block=False)

        logger.info("pynng sockets connected")

    def teardown_resource(self):
        if self._pub_trigger:
            self._pub_trigger.close()

        if self._sub_lores:
            self._sub_lores.close()

        if self._sub_hires:
            self._sub_hires.close()

    def _wait_for_lores_image(self) -> bytes:
        """Return the latest lores JPEG frame."""
        self.pause_wait_for_lores_while_hires_capture()
        with self._lores_data.condition:
            if not self._lores_data.condition.wait(timeout=0.5):
                raise TimeoutError("timeout receiving frames")
            return self._lores_data.data

    def _wait_for_still_file(self) -> Path:
        # TODO: get highres from the one camera selected.
        with NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix=f"{filename_str_time()}_still-wigglecam_", suffix=".jpg") as f:
            f.write(self._wait_for_lores_image())

            return Path(f.name)

    def _wait_for_multicam_files(self) -> list[Path]:
        """Trigger a capture request and collect hi-res images from all cameras."""
        assert self._pub_trigger
        assert self._sub_hires

        print("Job start")

        # Eindeutige ID für diese Umfrage
        job_uuid = uuid.uuid4()
        self._pub_trigger.send(job_uuid.bytes)

        job_folder = Path("tmp", f"job_{job_uuid}")
        job_folder.mkdir(exist_ok=True)

        results: list[Path] = []

        while True:
            try:
                data = self._sub_hires.recv()
                msg = ImageMessage.from_bytes(data)

                if msg.job_id != job_uuid:
                    # Antwort gehört zu alter Umfrage -> ignorieren
                    print("warning, old job id result received, ignored!")
                    continue

                fname = f"cam{msg.device_id}.jpg"
                fpath = Path(job_folder, fname)
                with open(fpath, "wb") as f:
                    f.write(msg.jpg_bytes)

                results.append(fpath)

                if len(results) == len(self._config.devices):
                    print("got all results, job completed!")
                    break

            except pynng.exceptions.Timeout as exc:
                print(f"job finished after 1s no more data, got {len(results)} result!")
                raise TimeoutError("timeout receiving frames") from exc

        return results

    def run_service(self):
        """Background loop to receive lores frames."""
        assert self._sub_lores
        while not self._stop_event.is_set():
            try:
                data = self._sub_lores.recv()
                msg = ImageMessage.from_bytes(data)

                if msg.device_id != self._config.index_cam_video:
                    continue  # drop messages from the not-selected nodes

                # store raw JPEG
                with self._lores_data.condition:
                    self._lores_data.data = msg.jpg_bytes
                    self._lores_data.condition.notify_all()
                self._frame_tick()
            except pynng.Timeout:
                continue
            except Exception as exc:
                logger.error(f"error receiving lores frame: {exc}")
                continue

        logger.info("run_service loop exited")

    def _on_configure_optimized_for_idle(self):
        pass

    def _on_configure_optimized_for_hq_preview(self):
        pass

    def _on_configure_optimized_for_hq_capture(self):
        pass

    def _on_configure_optimized_for_livestream_paused(self):
        pass
