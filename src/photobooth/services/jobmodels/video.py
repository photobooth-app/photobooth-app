from pathlib import Path

from ...database.models import Mediaitem, MediaitemTypes
from ..config.groups.actions import VideoConfigurationSet
from ..config.models.models import SinglePictureDefinition
from .base import JobModelBase


class JobModelVideo(JobModelBase):
    def __init__(self, configuration_set: VideoConfigurationSet):
        super().__init__(configuration_set, MediaitemTypes.video)

        self._total_captures_to_take = 1

        # self._validate_job()

    def get_phase1_singlepicturedefinition_per_index(self, index: int) -> SinglePictureDefinition:
        raise RuntimeError("no filter available for videos")

    def do_phase2_process_and_generate(self, phase1_files: list[Path], phase2_mediaitem: Mediaitem):
        raise RuntimeError("no filter available for videos")
