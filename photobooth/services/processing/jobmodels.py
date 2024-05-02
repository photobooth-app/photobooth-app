from enum import Enum
from typing import Literal, Union

from ...utils.helper import get_user_file
from ..config.groups.actions import (
    GroupAnimationProcessing,
    GroupCollageProcessing,
    GroupSingleImageProcessing,
    GroupVideoProcessing,
)
from ..config.models.models import AnimationMergeDefinition, CollageMergeDefinition
from ..mediacollection.mediaitem import MediaItem
from .countdowntimer import CountdownTimer

action_type_literal = Literal["image", "collage", "animation", "video"]


class JobModelBase:
    class Typ(str, Enum):
        undefined = "undefined"
        image = "image"
        collage = "collage"
        animation = "animation"
        video = "video"

    def __init__(
        self,
        job_config: Union[GroupSingleImageProcessing, GroupCollageProcessing, GroupAnimationProcessing, GroupVideoProcessing],
    ):
        self._typ: __class__.Typ = __class__.Typ.undefined
        self._job_config = job_config

        self._total_captures_to_take: int = 0
        self._ask_approval_each_capture: bool = False

        self._last_captured_mediaitem: MediaItem = None
        self._confirmed_captures_collection: list[MediaItem] = []

        # job model timer
        self._duration_user: float = 0
        self._countdown_timer: CountdownTimer = CountdownTimer()

    @staticmethod
    def _get_number_of_captures_from_merge_definition(merge_definition: Union[list[CollageMergeDefinition], list[AnimationMergeDefinition]]) -> int:
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
            f"typ={self._typ}, total_captures_to_take={self._total_captures_to_take}, "
            f"confirmed_captures_collection={self._confirmed_captures_collection}, last_capture={self._last_captured_mediaitem}"
        )

    def export(self) -> dict:
        """Export model as dict for UI (needds to be jsonserializable)

        following variables + the "self.state" variable (added by state machine automagically) will be exported.
        __class__.export() is used to json-serialize and send to frontend the current model state whenever need to update.

        Returns:
            dict: _description_
        """
        out = dict(
            state=self.state,
            typ=self._typ,
            total_captures_to_take=self.total_captures_to_take(),
            remaining_captures_to_take=self.remaining_captures_to_take(),
            number_captures_taken=self.number_captures_taken(),
            duration=self._duration_user,
            ask_user_for_approval=self.ask_user_for_approval(),
            confirmed_captures_collection=[captured_item.asdict() for captured_item in self._confirmed_captures_collection]
            if self._confirmed_captures_collection
            else [],
            last_captured_mediaitem=self._last_captured_mediaitem.asdict() if self._last_captured_mediaitem else None,
        )

        return out

    # external model processing controls
    def add_confirmed_capture_to_collection(self, captured_item: MediaItem):
        self._confirmed_captures_collection.append(captured_item)  # most recent is always at N pos., get latest with get_last_capture

    def last_capture_successful(self) -> bool:
        return self._last_captured_mediaitem is not None

    def set_last_capture(self, last_mediaitem: MediaItem):
        self._last_captured_mediaitem = last_mediaitem

    def get_last_capture(self) -> MediaItem:
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

    def jobtype_recording(self) -> bool:
        # to check if mode is video or HQ captures request
        if self._typ is __class__.Typ.video:
            return True
        else:
            return False

    # external countdown controls
    def start_countdown(self, duration_user: float, offset_camera: float = 0.0):
        """Countdown until camera shall trigger

        duration_user: Total time displayed to frontend user
        duration_capture: Time until camera is triggered to start capture

        Args:
            duration (float): _description_
        """

        # countdown is capped to maximum
        self._duration_user = duration_user if duration_user < CountdownTimer.TIMER_MAX_DURATION else CountdownTimer.TIMER_MAX_DURATION
        _offset_camera = offset_camera if (offset_camera <= duration_user) else duration_user

        self._countdown_timer.start(duration=(duration_user - _offset_camera))

    def wait_countdown_finished(self):
        self._countdown_timer.wait_countdown_finished()
        self._duration_user = 0


class JobModelImage(JobModelBase):
    def __init__(self, job_config: GroupSingleImageProcessing):
        super().__init__(job_config)
        self._typ: __class__.Typ = __class__.Typ.image

        self._total_captures_to_take = 1

        # self._validate_job()


class JobModelCollage(JobModelBase):
    def __init__(self, job_config: GroupCollageProcessing):
        super().__init__(job_config)
        self._typ: __class__.Typ = __class__.Typ.collage

        self._ask_approval_each_capture = job_config.ask_approval_each_capture
        self._total_captures_to_take = self._get_number_of_captures_from_merge_definition(job_config.merge_definition)

        # self._validate_job()


class JobModelAnimation(JobModelBase):
    def __init__(self, job_config: GroupAnimationProcessing):
        super().__init__(job_config)
        self._typ: __class__.Typ = __class__.Typ.animation

        self._ask_approval_each_capture = job_config.ask_approval_each_capture
        self._total_captures_to_take = self._get_number_of_captures_from_merge_definition(job_config.merge_definition)

        # self._validate_job()


class JobModelVideo(JobModelBase):
    def __init__(self, job_config: GroupVideoProcessing):
        super().__init__(job_config)
        self._typ: __class__.Typ = __class__.Typ.video

        self._total_captures_to_take = 1

        # self._validate_job()
