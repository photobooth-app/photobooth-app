from ..config.groups.actions import (
    AnimationConfigurationSet,
    AnimationProcessing,
)
from ..config.models.models import PilgramFilter, SinglePictureDefinition
from ..mediacollection.mediaitem import MediaItem, MediaItemTypes
from ..mediaprocessing.processes import (
    process_and_generate_animation,
)
from .base import JobModelBase


class JobModelAnimation(JobModelBase):
    def __init__(self, configuration_set: AnimationConfigurationSet):
        super().__init__(configuration_set)
        self._media_type: MediaItemTypes = MediaItemTypes.animation

        self._ask_approval_each_capture = configuration_set.jobcontrol.ask_approval_each_capture
        self._total_captures_to_take = self._get_number_of_captures_from_merge_definition(configuration_set.processing.merge_definition)

        # self._validate_job()

    def get_phase1_singlepicturedefinition_per_index(self, index: int = None) -> SinglePictureDefinition:
        processing: AnimationProcessing = self._configuration_set.processing
        # list only captured_images from merge_definition (excludes predefined)
        captured_images = [item for item in processing.merge_definition if not item.predefined_image]

        return SinglePictureDefinition(
            texts_enable=False,
            img_frame_enable=False,
            filter=captured_images[index].filter.value if index is not None else PilgramFilter.original.value,
        )

    def do_phase2_process_and_generate(self, phase2_mediaitem: MediaItem):
        process_and_generate_animation(self._confirmed_captures_collection, phase2_mediaitem)
