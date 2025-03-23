import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Generic, TypeVar
from uuid import UUID, uuid4

from statemachine import Event

from ... import PATH_PROCESSED, PATH_UNPROCESSED
from ...appconfig import appconfig
from ...database.models import Mediaitem, MediaitemTypes
from ...utils.countdowntimer import CountdownTimer
from ...utils.resizer import generate_resized
from ..aquisition import AquisitionService
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
from .machine.processingmachine import ProcessingMachine

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseConfigurationSet)


@dataclass
class Capture:
    filepath: Path
    uuid: UUID = field(default_factory=uuid4)


@dataclass
class CaptureSet:
    captures: list[Capture]
    uuid: UUID = field(default_factory=uuid4)


class JobModelBase(ABC, Generic[T]):
    # state = None

    def __init__(self, configuration_set: T, media_type: MediaitemTypes, aquisition_service: AquisitionService):
        self._status_sm = ProcessingMachine(self, state_field="state")
        self._status_sm.bind_events_to(self)

        self._configuration_set: T = configuration_set
        self._media_type: MediaitemTypes = media_type
        self._aquisition_service: AquisitionService = aquisition_service

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
        return f"{self.__class__.__name__}, {self._job_identifier=}, {self.total_captures_to_take=}"

    def export(self) -> dict[str, str | int | float | None | dict]:
        """Export model as dict for UI (needs to be jsonserializable)"""

        out = dict(
            typ=self._media_type.value,
            total_captures_to_take=self.total_captures_to_take,
            remaining_captures_to_take=self.remaining_captures_to_take,
            number_captures_taken=self.captures_taken,
            duration=self._countdown_timer._duration,
            present_mediaitem_id=str(self._present_mediaitem_id) if self._present_mediaitem_id else None,
            approval_id=str(self._approval_id) if self._approval_id else None,
            configuration_set=self._configuration_set.model_dump(mode="json"),
        )

        return out

    ## states logic to implement by the models

    @abstractmethod
    def on_enter_counting(self):
        self.start_countdown(appconfig.backends.countdown_camera_capture_offset)

    @abstractmethod
    def on_exit_counting(self):
        self.wait_countdown_finished()  # blocking call

    @abstractmethod
    def on_enter_capture(self): ...

    @abstractmethod
    def on_exit_capture(self): ...

    @abstractmethod
    def on_enter_approval(self): ...

    @abstractmethod
    def on_exit_approval(self, event: Event):
        def remove_files(capture_set: CaptureSet):
            for capture in capture_set.captures:
                try:
                    capture.filepath.unlink()
                except Exception as exc:
                    logger.warning(f"error removing file {exc}")

        if event == self._status_sm.next:
            logger.info("approved captureset")
            pass

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
    def on_enter_completed(self): ...

    @abstractmethod
    def on_exit_completed(self): ...

    @abstractmethod
    def on_enter_finished(self): ...

    @abstractmethod
    def new_filename(self) -> str:
        return datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")

    @property
    @abstractmethod
    def total_captures_to_take(self) -> int: ...

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
        original_filenamepath = self.new_filename()
        mediaitem = Mediaitem(
            id=uuid4(),
            job_identifier=self._job_identifier,
            media_type=MediaitemTypes.image,
            unprocessed=Path(PATH_UNPROCESSED, original_filenamepath),
            processed=Path(PATH_PROCESSED, original_filenamepath),
            pipeline_config=pipeline_config.model_dump(mode="json"),
            show_in_gallery=show_in_gallery,
        )

        # TODO: get some clever way to scale AND cache?
        # TODO: check if cache-generation checks for size and if already same as target, don't scale, just copy, clever trick done.
        generate_resized(capture_to_process, mediaitem.unprocessed, appconfig.mediaprocessing.full_still_length)
        process_phase1images(mediaitem.unprocessed, mediaitem)

        assert mediaitem.unprocessed.is_file()
        assert mediaitem.processed.is_file()

        return mediaitem

    def set_results(self, mediaitems: list[Mediaitem] | Mediaitem, present_uuid: UUID):
        """on enter completed, this has to be set by classes. present is sent to UI, the results are added to db"""
        if isinstance(mediaitems, list):
            self._result_mediaitems = mediaitems
        else:
            self._result_mediaitems = [mediaitems]

        self._present_mediaitem_id = present_uuid
