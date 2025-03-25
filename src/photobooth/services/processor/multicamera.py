import logging
from pathlib import Path
from uuid import uuid4

from statemachine import Event

from ... import PATH_PROCESSED, PATH_UNPROCESSED
from ...database.models import Mediaitem, MediaitemTypes
from ..aquisition import AquisitionService
from ..config.groups.actions import MulticameraConfigurationSet, SingleImageProcessing
from ..mediaprocessing.processes import process_and_generate_wigglegram
from .base import Capture, CaptureSet, JobModelBase

logger = logging.getLogger(__name__)


class JobModelMulticamera(JobModelBase[MulticameraConfigurationSet]):
    def __init__(self, configuration_set: MulticameraConfigurationSet, aquisition_service: AquisitionService):
        super().__init__(configuration_set, MediaitemTypes.multicamera, aquisition_service=aquisition_service)

        # self._validate_job()

    @property
    def total_captures_to_take(self) -> int:
        return 1

    def new_filename(self):
        return super().new_filename() + ".gif"

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
        ## PHASE 1:
        # postprocess each capture individually
        # list only captured_images from merge_definition (excludes predefined)
        phase1_mediaitems: list[Mediaitem] = []

        for capture_to_process in self._capture_sets[0].captures:  # for now only 1 set supported...
            logger.info(f"postprocessing capture: {capture_to_process=}")

            # until now just a very basic filter avail applied over all images
            _config = SingleImageProcessing(image_filter=self._configuration_set.processing.image_filter)

            mediaitem = self.complete_phase1image(
                capture_to_process.filepath,
                self._configuration_set.jobcontrol.show_individual_captures_in_gallery,
                _config,
            )
            phase1_mediaitems.append(mediaitem)

            logger.info(f"capture {mediaitem=} successful")

        assert len(phase1_mediaitems) > 0

        ## PHASE 2:
        # postprocess job as whole, create collage of single images, video...
        logger.info("start postprocessing phase 2")

        original_filenamepath = self.new_filename()
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

    def on_enter_finished(self): ...
