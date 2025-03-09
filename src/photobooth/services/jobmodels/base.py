from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, Literal, TypeVar
from uuid import UUID, uuid4

from ...database.models import Mediaitem, MediaitemTypes
from ...utils.countdowntimer import CountdownTimer
from ..config.groups.actions import BaseConfigurationSet, MultiImageJobControl
from ..config.models.models import AnimationMergeDefinition, CollageMergeDefinition, SinglePictureDefinition

action_type_literal = Literal["image", "collage", "animation", "video", "multicamera"]

T = TypeVar("T", bound=BaseConfigurationSet)


class JobModelBase(ABC, Generic[T]):
    def __init__(self, configuration_set: T, media_type: MediaitemTypes):
        self._media_type: MediaitemTypes = media_type  # alternative, could be derived from print(type(self).__name__)?
        self._configuration_set: T = configuration_set

        self._job_identifier: UUID = uuid4()

        self._total_captures_to_take: int = 0
        self._captures_taken: int = 0
        self._ask_approval_each_capture: bool = False
        self._last_captured_mediaitem_id: UUID | None = None

        # job model timer
        self._duration_user: float = 0
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
        return f"{self.__class__.__name__}, {self._job_identifier=}, {self._total_captures_to_take=}"

    def export(self) -> dict:
        """Export model as dict for UI (needds to be jsonserializable)

        following variables + the "self.state" variable (added by state machine automagically) will be exported.
        __class__.export() is used to json-serialize and send to frontend the current model state whenever need to update.

        Returns:
            dict: _description_
        """

        out = dict(
            state=self.state,  # type: ignore
            typ=self._media_type.value,
            total_captures_to_take=self.total_captures_to_take(),
            remaining_captures_to_take=self.remaining_captures_to_take(),
            number_captures_taken=self.get_captures_taken(),
            duration=self._duration_user,
            ask_user_for_approval=self.ask_user_for_approval(),
            last_captured_mediaitem_id=str(self._last_captured_mediaitem_id),
            configuration_set=self._configuration_set.model_dump(mode="json"),
        )

        return out

    # external model processing controls

    def total_captures_to_take(self) -> int:
        return self._total_captures_to_take

    def set_captures_taken(self, captures_taken: int):
        self._captures_taken = captures_taken

    def get_captures_taken(self) -> int:
        return self._captures_taken

    def remaining_captures_to_take(self) -> int:
        return self._total_captures_to_take - self._captures_taken

    def all_captures_done(self) -> bool:
        return self._captures_taken >= self._total_captures_to_take

    def ask_user_for_approval(self) -> bool:
        # display only for collage (multistep process if configured, otherwise always false)
        return self._ask_approval_each_capture

    # external countdown controls
    def start_countdown(self, offset: float = 0.0):
        """Countdown until camera shall trigger

        offset: Subtract from countdown to account for camera delays

        Args:
            duration (float): _description_
        """

        if self.get_captures_taken() == 0:
            duration_user = self._configuration_set.jobcontrol.countdown_capture
        else:
            # countdown_capture_second_following is only defined for multiimagejobs
            assert isinstance(self._configuration_set.jobcontrol, MultiImageJobControl)
            duration_user = self._configuration_set.jobcontrol.countdown_capture_second_following

        # if offset is less than duration, take it, else use duration for offset which results actually in 0
        # countdown because delay of camera is longer than desired countdown
        _offset = offset if (offset <= duration_user) else duration_user

        self._duration_user = duration_user

        self._countdown_timer.start(duration=(duration_user - _offset))

    def wait_countdown_finished(self):
        self._countdown_timer.wait_countdown_finished()
        self._duration_user = 0

    @abstractmethod
    def get_phase1_singlepicturedefinition_per_index(self, index: int) -> SinglePictureDefinition:
        pass

    @abstractmethod
    def do_phase2_process_and_generate(self, phase1_files: list[Path], phase2_mediaitem: Mediaitem):
        pass
