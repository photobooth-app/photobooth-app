import logging
from pathlib import Path
from typing import cast
from uuid import uuid4

from statemachine import Event

from ... import DATABASE_PATH, PATH_PROCESSED, PATH_UNPROCESSED, TMP_PATH
from ...database.models import Mediaitem, MediaitemTypes
from ...utils.helper import filename_str_time
from ...utils.multistereo_calibration.algorithms.simple import SimpleCalibrationUtil
from ..aquisition import AquisitionService
from ..backends.wigglecam import WigglecamBackend
from ..config.groups.actions import MulticameraConfigurationSet, SingleImageProcessing
from ..mediaprocessing.processes import process_and_generate_wigglegram
from .base import Capture, CaptureSet, JobModelBase

logger = logging.getLogger(__name__)


class JobModelMulticamera(JobModelBase[MulticameraConfigurationSet]):
    def __init__(self, configuration_set: MulticameraConfigurationSet, aquisition_service: AquisitionService):
        super().__init__(configuration_set, MediaitemTypes.multicamera, aquisition_service=aquisition_service)

        self.__cal_util = SimpleCalibrationUtil()
        self.__calibration_data_path = Path(DATABASE_PATH, "multicam_calibration_data")
        self.__calibration_is_valid: bool = False

        logger.info("setup calibration util to smooth multicam captures")

        try:
            self.__cal_util.load_calibration_data(self.__calibration_data_path)
            logger.info("calibration data loaded successfully")
        except ValueError as exc:
            logger.warning(f"no valid multicam calibration data found: {exc}, the results may suffer!")

        # validate that all device ids are still present in the current backend configuration and match with calibration data
        multicam_backend = cast(WigglecamBackend, self._aquisition_service._get_multicam_backend())
        expected_device_ids = multicam_backend.expected_device_ids()
        self.__calibration_is_valid = self.__cal_util.is_calibration_data_valid(expected_device_ids)
        if self.__calibration_is_valid:
            logger.info("found valid calibration data for all configured devices")
        else:
            logger.warning("calibration data is incomplete or invalid for the configured devices, the results may suffer!")

    @property
    def total_captures_to_take(self) -> int:
        return 1

    def on_enter_counting(self):
        self._aquisition_service.signalbackend_configure_optimized_for_hq_preview()

        super().on_enter_counting()

    def on_exit_counting(self):
        super().on_exit_counting()

    def on_enter_capture(self):
        logger.info(f"current capture ({self.captures_taken + 1}/{self.total_captures_to_take}, remaining {self.remaining_captures_to_take - 1})")

        self._aquisition_service.signalbackend_configure_optimized_for_hq_capture()

        captureset = CaptureSet([Capture(captured_file) for captured_file in self._aquisition_service.wait_for_multicam_files()])

        # add to tmp collection
        # update model so it knows the latest number of captures and the machine can react accordingly if finished
        self._capture_sets.append(captureset)

        logger.info(f"captureset {captureset} successful")

    def on_exit_capture(self): ...

    def on_enter_approval(self): ...

    def on_exit_approval(self, event: Event):
        super().on_exit_approval(event)

    def on_enter_completed(self):
        super().on_enter_completed()
        capture_set = self._capture_sets[0]  # for now only 1 set supported...
        files_to_process = [capture.filepath for capture in capture_set.captures]

        ## PHASE 0: for multicamera jobs, we need to see if a calibration is to apply before continue any processing.
        # calibration is used to improve the smoothness and align different camera views better.

        if self.__calibration_is_valid:
            logger.info("start multicamera calibration phase")
            files_preprocessed = self.__cal_util.align_all(files_to_process, Path(TMP_PATH), crop=True)
            logger.info("multicamera calibration phase completed")
        else:
            logger.warning("no valid calibration data found, skipping prealignment phase, results may suffer. Please run multicamera calibration.")
            files_preprocessed = files_to_process

        ## PHASE 1:
        # postprocess each capture individually
        # list only captured_images from merge_definition (excludes predefined)
        phase1_mediaitems: list[Mediaitem] = []

        for file_to_process in files_preprocessed:
            logger.info(f"postprocessing capture: {file_to_process=}")

            # until now just a very basic filter avail applied over all images
            _config = SingleImageProcessing(image_filter=self._configuration_set.processing.image_filter)

            mediaitem = self.complete_phase1image(
                file_to_process,
                self._configuration_set.jobcontrol.show_individual_captures_in_gallery,
                _config,
            )
            phase1_mediaitems.append(mediaitem)

            logger.info(f"capture {mediaitem=} successful")

        assert len(phase1_mediaitems) > 0

        ## PHASE 2:
        # postprocess job as whole, create collage of single images, video...
        logger.info("start postprocessing phase 2")

        original_filenamepath = Path(filename_str_time()).with_suffix(".gif")
        phase2_mediaitem = Mediaitem(
            id=uuid4(),
            job_identifier=self._job_identifier,
            media_type=self._media_type,
            unprocessed=Path(PATH_UNPROCESSED, original_filenamepath),
            processed=Path(PATH_PROCESSED, original_filenamepath),
            pipeline_config=self._configuration_set.processing.model_dump(mode="json"),
        )

        process_and_generate_wigglegram([item.processed for item in phase1_mediaitems], phase2_mediaitem)

        assert phase2_mediaitem.unprocessed.is_file()
        assert phase2_mediaitem.processed.is_file()

        # out to db/ui
        self.set_results([*phase1_mediaitems, phase2_mediaitem], phase2_mediaitem.id)

    def on_exit_completed(self): ...

    def on_enter_finished(self):
        super().on_enter_finished()
