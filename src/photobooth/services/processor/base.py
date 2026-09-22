from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Generic, TypeVar
from uuid import UUID, uuid4

from statemachine import Event

from ... import PATH_CAMERA_ORIGINAL, PATH_PROCESSED
from ...appconfig import appconfig
from ...database.models import Mediaitem, MediaitemTypes
from ...utils.countdowntimer import CountdownTimer
from ...utils.helper import filename_str_time
from ..collection import Cache
from ..config.groups.actions import (
    BaseConfigurationSet,
    MulticameraJobControl,
    MultiImageJobControl,
    SingleImageJobControl,
    SingleImageProcessing,
    VideoJobControl,
)
from ..config.models.models import AnimationMergeDefinition, CollageMergeDefinition
from ..mediaprocessing.processes import process_phase1images
from ..mediaprocessing.steps.image import get_plugin_long_running_filters
from .machine.processingmachine import ProcessingMachine
from .models import CaptureSet, UiCaptureDefinition, UiFrameOverlay, UiJobModel

if TYPE_CHECKING:
    from ..acquisition import AcquisitionService

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseConfigurationSet)


class JobModelBase(ABC, Generic[T]):
    # state = None
    _media_type: MediaitemTypes

    def __init__(self, configuration_set: T, acquisition_service: AcquisitionService):
        self._status_sm = ProcessingMachine(self, state_field="state")
        self._status_sm.bind_events_to(self)

        self._configuration_set: T = configuration_set
        self._acquisition_service: AcquisitionService = acquisition_service
        self._cache = Cache()

        self._job_identifier: UUID = uuid4()

        # intermediate-data to reuse in different states
        self._capture_sets: list[CaptureSet] = list()

        self._result_mediaitems: list[Mediaitem] | None = None
        self._present_mediaitem_id: UUID | None = None
        self._approval_id: UUID | None = None

        # job model timer
        self._countdown_timer: CountdownTimer = CountdownTimer()

    @staticmethod
    def _get_number_of_captures_from_merge_definition(merge_definition: list[CollageMergeDefinition] | list[AnimationMergeDefinition]) -> int:
        # item.predefined_image None or "" are considered as to capture aka not predefined
        predefined_images = [item.predefined_image for item in merge_definition if item.predefined_image]
        for predefined_image in predefined_images:
            # preflight check here without use.
            if not Path(predefined_image).is_file():
                raise RuntimeError(f"predefined image {predefined_image} not found!")

        total_images_in_collage = len(merge_definition)
        fixed_images = len(predefined_images)

        captures_to_take = total_images_in_collage - fixed_images

        return captures_to_take

    def __repr__(self):
        return f"<{self.__class__.__name__}> job-id={self._job_identifier} total captures to take={self.total_captures_to_take}"

    @property
    def is_long_running_filter(self) -> bool:
        long_running_filters = get_plugin_long_running_filters()
        if not long_running_filters:
            return False

        if hasattr(self._configuration_set, "processing") and hasattr(self._configuration_set.processing, "image_filter"):
            filter_val = self._configuration_set.processing.image_filter
            filter_name = filter_val.value if hasattr(filter_val, "value") else str(filter_val)
            if filter_name in long_running_filters:
                return True
        return False

    @property
    def latest_capture_id(self) -> str | None:
        if self._capture_sets and self._capture_sets[-1].captures:
            return str(self._capture_sets[-1].captures[-1].uuid)
        return None

    def export(self) -> UiJobModel:
        """Export model as dict for UI (needs to be jsonserializable)"""
        return UiJobModel(
            typ=self._media_type,
            total_captures_to_take=self.total_captures_to_take,
            remaining_captures_to_take=self.remaining_captures_to_take,
            number_captures_taken=self.captures_taken,
            duration=self._countdown_timer._duration + appconfig.cameras.countdown_camera_capture_offset if self._countdown_timer._duration else 0,
            present_mediaitem_id=str(self._present_mediaitem_id) if self._present_mediaitem_id else None,
            approval_id=str(self._approval_id) if self._approval_id else None,
            frame_overlay=self.frame_overlay,
            captures_definition=self.captures_definition,
            is_long_running_filter=self.is_long_running_filter,
            latest_capture_id=self.latest_capture_id,
        )

    ## states logic to implement by the models

    @abstractmethod
    def on_enter_counting(self):
        self.start_countdown(appconfig.cameras.countdown_camera_capture_offset)

    @abstractmethod
    def on_exit_counting(self):
        self.wait_countdown_finished()  # blocking call

    @abstractmethod
    def on_enter_capture(self):
        """capture now (enter)"""

    @abstractmethod
    def on_exit_capture(self):
        """capture now (exit)"""

    @abstractmethod
    def on_enter_approval(self):
        """ask for approval"""

    @abstractmethod
    def on_exit_approval(self, event: Event):
        """eval user / automated input got from transition"""

        def remove_files(capture_set: CaptureSet):
            for capture in capture_set.captures:
                try:
                    capture.filepath.unlink()
                except Exception as exc:
                    logger.warning(f"error removing file {exc}")

        if event == self._status_sm.next:
            logger.info("approved captureset")

        if event == self._status_sm.reject:
            logger.info("rejected captureset, remove last captureset")
            captureset = self._capture_sets.pop()
            remove_files(captureset)

        if event == self._status_sm.abort:
            logger.info("abort job, remove all capturesets")
            for captureset in self._capture_sets:
                remove_files(captureset)

            self._capture_sets.clear()

    @abstractmethod
    def on_enter_completed(self):
        """when ALL captures are completed for the job"""
        # self._acquisition_service.signalbackend_configure_optimized_for_idle()

    @abstractmethod
    def on_exit_completed(self):
        """when ALL captures are completed for the job"""

    @abstractmethod
    def on_enter_finished(self):
        """the very last step, used to notify the ui the statemachin is going done now"""

    @property
    @abstractmethod
    def total_captures_to_take(self) -> int:
        """number of captures to take during a job"""

    @property
    @abstractmethod
    def captures_definition(self) -> UiCaptureDefinition | None:
        """ui definition for current capture to take during a job"""

    @property
    @abstractmethod
    def frame_overlay(self) -> UiFrameOverlay | None:
        """overlay used during a job"""

    @property
    def captures_taken(self) -> int:
        return len(self._capture_sets)

    @property
    def remaining_captures_to_take(self) -> int:
        return self.total_captures_to_take - self.captures_taken

    def sm_cond_all_captures_done(self) -> bool:
        return self.captures_taken >= self.total_captures_to_take

    def sm_cond_ask_user_for_approval(self) -> bool:
        # display only for collage (multistep process if configured, otherwise always false)
        if isinstance(self._configuration_set.jobcontrol, MultiImageJobControl):
            return self._configuration_set.jobcontrol.ask_approval_each_capture
        else:
            return False

    def start_countdown(self, offset: float = 0.0):
        if isinstance(self._configuration_set.jobcontrol, SingleImageJobControl | VideoJobControl | MulticameraJobControl):
            duration_user = self._configuration_set.jobcontrol.countdown_capture
        elif isinstance(self._configuration_set.jobcontrol, MultiImageJobControl):
            if self.captures_taken == 0:
                duration_user = self._configuration_set.jobcontrol.countdown_capture
            else:  # countdown_capture_second_following is for multiimagejobs to shorten 2nd+ shoot
                duration_user = self._configuration_set.jobcontrol.countdown_capture_second_following
        else:
            raise AssertionError("jobcontrol is neither SingleImageJobControl nor MultiImageJobControl!")

        # if offset is less than duration, take it, else use duration for offset which results actually in 0
        # countdown because delay of camera is longer than desired countdown
        _offset = offset if (offset <= duration_user) else duration_user

        self._countdown_timer.start(duration=(duration_user - _offset))

    def wait_countdown_finished(self):
        self._countdown_timer.wait_countdown_finished()

    def complete_phase1image(self, capture_to_process: Path, show_in_gallery: bool, pipeline_config: SingleImageProcessing) -> Mediaitem:
        original_filenamepath = Path(f"{filename_str_time()}{'' if show_in_gallery else '_hidden'}").with_suffix(capture_to_process.suffix)

        # very first, move the capture_to_process to originals. if anything later fails, at least we got the file in safe place.
        captured_original = capture_to_process.rename(Path(PATH_CAMERA_ORIGINAL, original_filenamepath))

        mediaitem = Mediaitem(
            id=uuid4(),
            job_identifier=self._job_identifier,
            media_type="image",
            processed=Path(PATH_PROCESSED, original_filenamepath),
            captured_original=captured_original,
            pipeline_config=pipeline_config.model_dump(mode="json"),
            show_in_gallery=show_in_gallery,
        )

        cacheditem = self._cache.get_cached_repr(mediaitem, "full", processed=False)
        process_phase1images(cacheditem.filepath, mediaitem)

        assert mediaitem.processed.is_file()
        assert mediaitem.captured_original and mediaitem.captured_original.is_file()

        return mediaitem

    def set_results(self, mediaitems: list[Mediaitem] | Mediaitem, present_uuid: UUID):
        """on enter completed, this has to be set by classes. present is sent to UI, the results are added to db"""
        if isinstance(mediaitems, list):
            self._result_mediaitems = mediaitems
        else:
            self._result_mediaitems = [mediaitems]

        self._present_mediaitem_id = present_uuid
