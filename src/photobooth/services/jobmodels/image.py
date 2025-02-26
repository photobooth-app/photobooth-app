from pathlib import Path

from ...database.models import Mediaitem, MediaitemTypes
from ..config.groups.actions import SingleImageConfigurationSet
from ..config.models.models import SinglePictureDefinition
from .base import JobModelBase


class JobModelImage(JobModelBase):
    def __init__(self, configuration_set: SingleImageConfigurationSet):
        super().__init__(configuration_set, MediaitemTypes.image)
        self._total_captures_to_take = 1

        # self._validate_job()

    def get_phase1_singlepicturedefinition_per_index(self, index: int) -> SinglePictureDefinition:
        # index for jobmodelimage not used, just pass 1:1 to out
        return SinglePictureDefinition(**self._configuration_set.processing.model_dump())

    def do_phase2_process_and_generate(self, phase1_files: list[Path], phase2_mediaitem: Mediaitem):
        raise RuntimeError("no phase2 mediageneration for images")
