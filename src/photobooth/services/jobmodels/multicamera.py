from pathlib import Path

from ...database.models import Mediaitem, MediaitemTypes
from ..config.groups.actions import MulticameraConfigurationSet, MulticameraProcessing
from ..config.models.models import SinglePictureDefinition
from ..mediaprocessing.processes import process_and_generate_wigglegram
from .base import JobModelBase


class JobModelMulticamera(JobModelBase):
    def __init__(self, configuration_set: MulticameraConfigurationSet):
        super().__init__(configuration_set, MediaitemTypes.multicamera)

        self._total_captures_to_take = 1

        # self._validate_job()

    def get_phase1_singlepicturedefinition_per_index(self, index: int) -> SinglePictureDefinition:
        processing: MulticameraProcessing = self._configuration_set.processing

        # until now just a very basic filter avail applied over all images

        return SinglePictureDefinition(image_filter=processing.image_filter)

    def do_phase2_process_and_generate(self, phase1_files: list[Path], phase2_mediaitem: Mediaitem):
        process_and_generate_wigglegram(phase1_files, phase2_mediaitem)
