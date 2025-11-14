import logging
import uuid
from pathlib import Path
from threading import Condition

import pynng
from wigglecam.dto import ImageMessage

from ... import DATABASE_PATH, TMP_PATH
from ...utils.multistereo_calibration.algorithms.simple import SimpleCalibrationUtil
from ..config.groups.cameras import GroupCameraWigglecam
from .abstractbackend import AbstractBackend, GeneralBytesResult

logger = logging.getLogger(__name__)
CALIBRATION_DATA_PATH = Path(DATABASE_PATH, "multicam_calibration_data")


class CalibrationMixin:
    """Calibration is part of the backends and currently only for the multicam, so we can keep it here.
    Maybe in future we can also support calibrate intrinisics of picamera to remove lens distortions and
    improve stereo calibration

    The backends only use a subset of the calibration util: load and align, so only these are exposed.
    Calibration routine and saving is done in the multicam-tool which is actually living in the api backend endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cal_util = SimpleCalibrationUtil()
        self._calibration_data_path = CALIBRATION_DATA_PATH
        self._calibration_is_valid: bool = False

    def load_calibration(self, expected_device_ids: tuple[int, ...]):
        try:
            self._cal_util.load_calibration_data(self._calibration_data_path)
            logger.info("Calibration data loaded successfully")
        except ValueError as exc:
            logger.warning(f"No valid multicam calibration loaded, the results may suffer. Error: {exc}")
        else:
            # validate that all device ids are still present in the current backend configuration and match with calibration data
            self._calibration_is_valid = self._cal_util.is_calibration_data_valid(expected_device_ids)
            if self._calibration_is_valid:
                # we just check the number of devices, though. there is no check for the exact camera.
                logger.info("Found valid calibration data for all configured devices.")
            else:
                logger.warning("Calibration data is incomplete or invalid for the configured devices, the results may suffer!")

    def align_all(self, files_in: list[Path], out_dir: Path, crop: bool = True) -> list[Path]:
        if self._calibration_is_valid:
            logger.debug("post_process_multicam_set completed")

            return self._cal_util.align_all(files_in, out_dir, crop)
        else:
            logger.warning("no valid calibration data found, skipping prealignment phase, results may suffer. Please run multicamera calibration.")

            return files_in


class WigglecamBackend(AbstractBackend, CalibrationMixin):
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

        self.load_calibration(expected_device_ids)

        logger.info("pynng sockets connected")

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

    def postprocess_multicam_set(self, files_in: list[Path], out_dir: Path) -> list[Path]:
        files_preprocessed = self.align_all(files_in, out_dir=out_dir, crop=True)

        return files_preprocessed

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

                # if msg.device_id != self._config.index_cam_video:
                #     continue  # drop messages from the not-selected nodes

                # store raw JPEG of all devices. TODO: might need to limit to only one device if it gets overwhelming for low end SBC
                with self._lores_data[msg.device_id].condition:
                    self._lores_data[msg.device_id].data = msg.jpg_bytes
                    self._lores_data[msg.device_id].condition.notify_all()
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
