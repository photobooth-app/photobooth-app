import logging

from statemachine import Event

from ...database.models import MediaitemTypes
from ..aquisition import AquisitionService
from ..config.groups.actions import SingleImageConfigurationSet
from .base import Capture, CaptureSet, JobModelBase

logger = logging.getLogger(__name__)


class JobModelImage(JobModelBase[SingleImageConfigurationSet]):
    def __init__(self, configuration_set: SingleImageConfigurationSet, aquisition_service: AquisitionService):
        super().__init__(configuration_set, MediaitemTypes.image, aquisition_service=aquisition_service)

        # self._validate_job()

    @property
    def total_captures_to_take(self) -> int:
        return 1

    def new_filename(self):
        return super().new_filename() + ".jpg"

    def on_enter_counting(self):
        self._aquisition_service.signalbackend_configure_optimized_for_hq_preview()

        super().on_enter_counting()

    def on_exit_counting(self):
        super().on_exit_counting()

    def on_enter_capture(self):
        logger.info(f"current capture ({self.captures_taken + 1}/{self.total_captures_to_take}, remaining {self.remaining_captures_to_take - 1})")

        self._aquisition_service.signalbackend_configure_optimized_for_hq_capture()

        captureset = CaptureSet([Capture(self._aquisition_service.wait_for_still_file())])

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
        capture_to_process = self._capture_sets[0].captures[0].filepath
        mediaitem = self.complete_phase1image(capture_to_process, True, self._configuration_set.processing)

        # out to db/ui
        self.set_results(mediaitem, mediaitem.id)

        logger.info(f"capture {mediaitem=} successful")

    def on_exit_completed(self): ...

    def on_enter_finished(self): ...
