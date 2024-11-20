from ..config.groups.actions import (
    MulticameraConfigurationSet,
    MulticameraProcessing,
)
from ..config.models.models import SinglePictureDefinition
from ..mediacollection.mediaitem import MediaItem, MediaItemTypes
from .base import JobModelBase


class JobModelMulticamera(JobModelBase):
    def __init__(self, configuration_set: MulticameraConfigurationSet):
        super().__init__(configuration_set)
        self._media_type: MediaItemTypes = MediaItemTypes.multicamera

        self._total_captures_to_take = 1

        # self._validate_job()

    def get_phase1_singlepicturedefinition_per_index(self, index: int = None) -> SinglePictureDefinition:
        processing: MulticameraProcessing = self._configuration_set.processing

        # until now just a very basic filter avail applied over all images

        return SinglePictureDefinition(
            filter=processing.filter.value,
        )

    def do_phase2_process_and_generate(self, phase2_mediaitem: MediaItem):
        raise NotImplementedError("not yet implemented.")
        # process_and_generate_multicamera(self._confirmed_captures_collection, phase2_mediaitem)
