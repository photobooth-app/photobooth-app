import logging
import uuid
from pathlib import Path
from threading import Condition

import pynng
from wigglecam.dto import ImageMessage

from ... import DATABASE_PATH, TMP_PATH
from ..config.groups.cameras import GroupCameraWigglecam
from .abstractbackend import AbstractBackend, GeneralBytesResult

logger = logging.getLogger(__name__)
CALIBRATION_DATA_PATH = Path(DATABASE_PATH, "multicam_calibration_data")


class WigglecamBackend(AbstractBackend):
    def __init__(self, config: GroupCameraWigglecam):
        super().__init__()
        self._config = config

        self._lores_data: list[GeneralBytesResult] | None = None
        self._pub_trigger: pynng.Pub0 | None = None
        self._sub_lores: pynng.Sub0 | None = None
        self._sub_hires: pynng.Sub0 | None = None

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def expected_device_ids(self) -> tuple[int, ...]:  # The tuple[int, ...] syntax means a tuple containing any number of integers.
        return tuple(range(len(self._config.devices)))

    def setup_resource(self):
        expected_device_ids = self.expected_device_ids()

        if self._config.index_cam_stills not in expected_device_ids:
            raise RuntimeError(f"Configuration error: The device foreseen for stills on index {self._config.index_cam_stills} is not available!")
        if self._config.index_cam_video not in expected_device_ids:
            raise RuntimeError(f"Configuration error: The device foreseen for video on index {self._config.index_cam_video} is not available!")

        def cb_connected(pipe: pynng.Pipe):
            logger.debug(f"Connected to wigglecam node: {pipe.url}")

        # host also subscribes to the hires replies
        self._pub_trigger = pynng.Pub0()
        self._pub_trigger.add_post_pipe_connect_cb(cb_connected)
        for node in self._config.devices:
            self._pub_trigger.dial(f"tcp://{node.address}:{node.base_port + 0}", block=False)

        # Listen for lores streams
        self._sub_lores = pynng.Sub0()
        self._sub_lores.add_post_pipe_connect_cb(cb_connected)
        self._sub_lores.subscribe(b"")
        self._sub_lores.recv_timeout = 1000
        for node in self._config.devices:
            self._sub_lores.dial(f"tcp://{node.address}:{node.base_port + 1}", block=False)

        # Setup Sub for hires
        self._sub_hires = pynng.Sub0()
        self._sub_hires.add_post_pipe_connect_cb(cb_connected)
        self._sub_hires.subscribe(b"")
        self._sub_hires.recv_timeout = 3000
        for node in self._config.devices:
            self._sub_hires.dial(f"tcp://{node.address}:{node.base_port + 2}", block=False)

        self._lores_data = [GeneralBytesResult(data=b"", condition=Condition()) for _ in expected_device_ids]
        # Sanity check: ensure distinct objects were created
        assert all(a is not b for i, a in enumerate(self._lores_data) for j, b in enumerate(self._lores_data) if i != j)

    def teardown_resource(self):
        if self._pub_trigger:
            self._pub_trigger.close()

        if self._sub_lores:
            self._sub_lores.close()

        if self._sub_hires:
            self._sub_hires.close()

    def _wait_for_lores_image(self, index_subdevice: int = 0) -> bytes:
        assert self._lores_data

        self.pause_wait_for_lores_while_hires_capture()
        with self._lores_data[index_subdevice].condition:
            if not self._lores_data[index_subdevice].condition.wait(timeout=0.5):
                raise TimeoutError("timeout receiving frames")
            return self._lores_data[index_subdevice].data

    def _wait_for_still_file(self) -> Path:
        # TODO: get highres from the one camera selected, for now get all and return the selected one
        captured_filepaths = self.__request_multicam_files()
        return captured_filepaths[self._config.index_cam_stills]

    def _wait_for_multicam_files(self) -> list[Path]:
        captured_filepaths = self.__request_multicam_files()
        return captured_filepaths

    def __request_multicam_files(self) -> list[Path]:
        """Trigger a capture request and collect hi-res images from all cameras."""
        assert self._pub_trigger
        assert self._sub_hires
        expected_device_ids = self.expected_device_ids()

        job_uuid = uuid.uuid4()
        self._pub_trigger.send(job_uuid.bytes)

        job_folder = Path(TMP_PATH, f"multicam_job_{job_uuid}")
        job_folder.mkdir(exist_ok=True)

        logger.info(f"triggered multicam still capture, waiting for results... (job id: {job_uuid})")

        # Collect results keyed by device_id
        results: dict[int, Path] = {}

        while len(results) < len(expected_device_ids):
            try:
                data = self._sub_hires.recv()
                msg = ImageMessage.from_bytes(data)

                if msg.job_id != job_uuid:
                    logger.warning("warning, old job id result received, ignored!")
                    continue

                if msg.device_id in results:
                    logger.warning("warning, duplicate device id result received, ignored!")
                    continue

                fname = f"wigglenode_device_id-{msg.device_id}.jpg"
                fpath = job_folder / fname
                with open(fpath, "wb") as f:
                    f.write(msg.jpg_bytes)

                results[msg.device_id] = fpath

            except pynng.exceptions.Timeout as exc:
                if results:
                    missing = set(expected_device_ids) - results.keys()
                    logger.error(f"got partial results from device-ids {set(results)}, missing from device_ids {missing}!")
                else:
                    logger.error("timeout waiting for hires stills, no results received!")
                raise TimeoutError("timeout receiving stills from nodes") from exc

        logger.info(f"Finished receiving images. Results from device-ids '{set(results)}' saved to {job_folder}")

        # Build ordered list according to config.devices
        files_out = [results[i] for i in range(len(self._config.devices)) if i in results]

        if len(files_out) != len(expected_device_ids):
            raise RuntimeError("error collecting all files, mismatch in number of devices vs collected files")

        return files_out

    def run_service(self):
        """Background loop to receive lores frames."""
        assert self._sub_lores
        assert self._lores_data

        while not self._stop_event.is_set():
            try:
                data = self._sub_lores.recv()  # timeout after set time during setup
                msg = ImageMessage.from_bytes(data)

                # store raw JPEG of all devices. TODO: might need to limit to only one device if it gets overwhelming for low end SBC
                with self._lores_data[msg.device_id].condition:
                    self._lores_data[msg.device_id].data = msg.jpg_bytes
                    self._lores_data[msg.device_id].condition.notify_all()

                if msg.device_id == self._config.index_cam_video:
                    self._frame_tick()

            except pynng.Timeout:
                # this is used to start another loop and have chance to check for a stop_event
                continue
            except Exception as exc:
                logger.error(f"error receiving lores frame: {exc}")
                continue

        logger.debug("run_service loop exited")

    def _on_configure_optimized_for_idle(self): ...

    def _on_configure_optimized_for_hq_preview(self): ...

    def _on_configure_optimized_for_hq_capture(self): ...

    def _on_configure_optimized_for_livestream_paused(self): ...
