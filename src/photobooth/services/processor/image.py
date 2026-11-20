import logging

from statemachine import Event

from ..acquisition import AcquisitionService
from ..config.groups.actions import SingleImageConfigurationSet
from ..mediaprocessing.steps.image import get_frame_transparent_size
from .base import JobModelBase
from .models import Capture, CaptureSet, UiCaptureDefinition, UiFrameOverlay

logger = logging.getLogger(__name__)


class JobModelImage(JobModelBase[SingleImageConfigurationSet]):
    _media_type = "image"

    def __init__(self, configuration_set: SingleImageConfigurationSet, acquisition_service: AcquisitionService):
        super().__init__(configuration_set, acquisition_service=acquisition_service)

        # self._validate_job()

    @property
    def total_captures_to_take(self) -> int:
        return 1

    @property
    def captures_definition(self) -> UiCaptureDefinition | None:
        # frame hidden in preview: crop livestream to the transparent area to match the final image.
        processing = self._configuration_set.processing
        if processing.img_frame_enable and processing.img_frame_file and not processing.img_frame_preview_enable:
            try:
                width, height = get_frame_transparent_size(processing.img_frame_file)
            except Exception as exc:
                logger.warning(f"cannot determine size of frame {processing.img_frame_file}, livestream is not cropped: {exc}")
                return None

            return UiCaptureDefinition("-", width=width, height=height)

        return None

    @property
    def frame_overlay(self) -> UiFrameOverlay | None:
        processing = self._configuration_set.processing
        if processing.img_frame_enable and processing.img_frame_preview_enable and processing.img_frame_file:
            return UiFrameOverlay(
                processing.img_frame_file,
                mirror_effect=processing.img_frame_preview_mirror,
            )

        return None

    def on_enter_counting(self):
        self._acquisition_service.thrill_still()
        # self._acquisition_service.signalbackends_hq_thrill()

        super().on_enter_counting()

    def on_exit_counting(self):
        super().on_exit_counting()

    def on_enter_capture(self):
        logger.info(f"current capture ({self.captures_taken + 1}/{self.total_captures_to_take}, remaining {self.remaining_captures_to_take - 1})")

        captureset = CaptureSet([Capture(self._acquisition_service.wait_for_still_file())])

        # add to tmp collection
        # update model so it knows the latest number of captures and the machine can react accordingly if finished
        self._capture_sets.append(captureset)

        # logger.info(f"captureset {captureset} successful") # not helpful to output normally.

    def on_exit_capture(self):
        pass

    def on_enter_approval(self):
        pass

    def on_exit_approval(self, event: Event):
        super().on_exit_approval(event)

    def on_enter_completed(self):

        ## PHASE 1:
        # postprocess each capture individually
        capture_to_process = self._capture_sets[0].captures[0].filepath
        mediaitem = self.complete_phase1image(capture_to_process, True, self._configuration_set.processing)

        # out to db/ui
        self.set_results(mediaitem, mediaitem.id)

        logger.info(f"capture {mediaitem.processed} processed")

    def on_exit_completed(self):
        pass

    def on_enter_finished(self):
        pass
