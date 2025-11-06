import logging
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Condition

import pynng

from ... import DATABASE_PATH, TMP_PATH
from ...utils.multistereo_calibration.algorithms.simple import SimpleCalibrationUtil
from ..config.groups.cameras import GroupCameraWigglecam
from .abstractbackend import AbstractBackend, GeneralBytesResult

logger = logging.getLogger(__name__)
CALIBRATION_DATA_PATH = Path(DATABASE_PATH, "multicam_calibration_data")


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

        self.__cal_util = SimpleCalibrationUtil()
        self.__calibration_data_path = CALIBRATION_DATA_PATH
        self.__calibration_is_valid: bool = False

        try:
            self.__cal_util.load_calibration_data(self.__calibration_data_path)
            logger.info("Calibration data loaded successfully")
        except ValueError as exc:
            logger.warning(f"No valid multicam calibration loaded, the results may suffer. Error: {exc}")
        else:
            # validate that all device ids are still present in the current backend configuration and match with calibration data
            expected_device_ids = self.expected_device_ids()
            self.__calibration_is_valid = self.__cal_util.is_calibration_data_valid(expected_device_ids)
            if self.__calibration_is_valid:
                # we just check the number of devices, though. there is no check for the exact camera.
                logger.info("Found valid calibration data for all configured devices.")
            else:
                logger.warning("Calibration data is incomplete or invalid for the configured devices, the results may suffer!")

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def expected_device_ids(self) -> tuple[int, ...]:  # The tuple[int, ...] syntax means a tuple containing any number of integers.
        return tuple(range(len(self._config.devices)))

    def setup_resource(self):
        max_index = max(self._config.index_cam_stills, self._config.index_cam_video)
        if max_index > len(self._config.devices) - 1:
            raise RuntimeError(f"Configuration error: index out of range! {max_index=} whereas max_index allowed={len(self._config.devices) - 1}")

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
        # TODO: get highres from the one camera selected, for now get all and return the selected one
        captured_filepaths = self.__request_multicam_files()
        return captured_filepaths[self._config.index_cam_stills]

    def _wait_for_multicam_files(self) -> list[Path]:
        captured_filepaths = self.__request_multicam_files()
        return captured_filepaths

    def postprocess_multicam_set(self, files_in: list[Path], out_dir: Path) -> list[Path]:
        if self.__calibration_is_valid:
            files_preprocessed = self.__cal_util.align_all(files_in, out_dir=out_dir, crop=True)
            logger.debug("post_process_multicam_set completed")
        else:
            logger.warning("no valid calibration data found, skipping prealignment phase, results may suffer. Please run multicamera calibration.")
            files_preprocessed = files_in

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

        logger.debug("run_service loop exited")

    def _on_configure_optimized_for_idle(self):
        pass

    def _on_configure_optimized_for_hq_preview(self):
        pass

    def _on_configure_optimized_for_hq_capture(self):
        pass

    def _on_configure_optimized_for_livestream_paused(self):
        pass
