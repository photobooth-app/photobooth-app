from ..config.groups.actions import (
    VideoConfigurationSet,
)
from ..config.models.models import SinglePictureDefinition
from ..mediacollection.mediaitem import MediaItem, MediaItemTypes
from .base import JobModelBase


class JobModelVideo(JobModelBase):
    def __init__(self, configuration_set: VideoConfigurationSet):
        super().__init__(configuration_set)
        self._media_type: MediaItemTypes = MediaItemTypes.video

        self._total_captures_to_take = 1

        # self._validate_job()

    def get_phase1_singlepicturedefinition_per_index(self, index: int = None) -> SinglePictureDefinition:
        raise RuntimeError("no filter available for videos")

    def do_phase2_process_and_generate(self, phase2_mediaitem: MediaItem):
        raise RuntimeError("no filter available for videos")