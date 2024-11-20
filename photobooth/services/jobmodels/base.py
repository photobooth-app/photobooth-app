from abc import ABC, abstractmethod
from typing import Literal

from ...utils.countdowntimer import CountdownTimer
from ...utils.helper import get_user_file
from ..config.groups.actions import (
    AnimationConfigurationSet,
    CollageConfigurationSet,
    MulticameraConfigurationSet,
    MultiImageJobControl,
    SingleImageConfigurationSet,
    VideoConfigurationSet,
)
from ..config.models.models import AnimationMergeDefinition, CollageMergeDefinition, SinglePictureDefinition
from ..mediacollection.mediaitem import MediaItem, MediaItemTypes

action_type_literal = Literal["image", "collage", "animation", "video", "multicamera"]


class JobModelBase(ABC):
    def __init__(
        self,
        configuration_set: SingleImageConfigurationSet
        | CollageConfigurationSet
        | AnimationConfigurationSet
        | VideoConfigurationSet
        | MulticameraConfigurationSet,
    ):
        self._media_type: MediaItemTypes = None
        self._configuration_set = configuration_set

        self._total_captures_to_take: int = 0
        self._ask_approval_each_capture: bool = False

        self._last_captured_mediaitem: MediaItem = None
        self._confirmed_captures_collection: list[MediaItem] = []

        # job model timer
        self._duration_user: float = 0
        self._countdown_timer: CountdownTimer = CountdownTimer()

    @staticmethod
    def _get_number_of_captures_from_merge_definition(merge_definition: list[CollageMergeDefinition] | list[AnimationMergeDefinition]) -> int:
        # item.predefined_image None or "" are considered as to capture aka not predefined
        predefined_images = [item.predefined_image for item in merge_definition if item.predefined_image]
        for predefined_image in predefined_images:
            try:
                # preflight check here without use.
                _ = get_user_file(predefined_image)
            except FileNotFoundError as exc:
                raise RuntimeError(f"predefined image {predefined_image} not found!") from exc

        total_images_in_collage = len(merge_definition)
        fixed_images = len(predefined_images)

        captures_to_take = total_images_in_collage - fixed_images

        return captures_to_take

    def __repr__(self):
        return (
            f"{self.__class__.__name__}, total_captures_to_take={self._total_captures_to_take}, "
            f"confirmed_captures_collection={self._confirmed_captures_collection}, last_capture={self._last_captured_mediaitem}"
        )

    def export(self) -> dict:
        """Export model as dict for UI (needds to be jsonserializable)

        following variables + the "self.state" variable (added by state machine automagically) will be exported.
        __class__.export() is used to json-serialize and send to frontend the current model state whenever need to update.

        Returns:
            dict: _description_
        """
        confirmed_captures_collection = (
            [captured_item.asdict() for captured_item in self._confirmed_captures_collection] if self._confirmed_captures_collection else []
        )
        last_captured_mediaitem = self._last_captured_mediaitem.asdict() if self._last_captured_mediaitem else None

        out = dict(
            state=self.state,
            typ=self._media_type.value,
            total_captures_to_take=self.total_captures_to_take(),
            remaining_captures_to_take=self.remaining_captures_to_take(),
            number_captures_taken=self.number_captures_taken(),
            duration=self._duration_user,
            ask_user_for_approval=self.ask_user_for_approval(),
            confirmed_captures_collection=confirmed_captures_collection,
            last_captured_mediaitem=last_captured_mediaitem,
        )

        return out

    # external model processing controls
    def add_confirmed_capture_to_collection(self, captured_item: MediaItem):
        self._confirmed_captures_collection.append(captured_item)  # most recent is always at N pos., get latest with get_last_capture

    def last_capture_successful(self) -> bool:
        return self._last_captured_mediaitem is not None

    def set_last_capture(self, last_mediaitem: MediaItem | list[MediaItem]):
        self._last_captured_mediaitem = last_mediaitem

    def get_last_capture(self) -> MediaItem | list[MediaItem]:
        return self._last_captured_mediaitem

    def total_captures_to_take(self) -> int:
        return self._total_captures_to_take

    def remaining_captures_to_take(self) -> int:
        return self._total_captures_to_take - len(self._confirmed_captures_collection)

    def number_captures_taken(self) -> int:
        return len(self._confirmed_captures_collection)

    def all_captures_confirmed(self) -> bool:
        return len(self._confirmed_captures_collection) >= self._total_captures_to_take

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

        if self.number_captures_taken() == 0:
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
    def get_phase1_singlepicturedefinition_per_index(index: int = None) -> SinglePictureDefinition:
        pass

    @abstractmethod
    def do_phase2_process_and_generate(self, phase2_mediaitem: MediaItem):
        pass
