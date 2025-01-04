from ...database.models import MediaitemTypes, V3Mediaitem
from ..config.groups.actions import CollageConfigurationSet, CollageProcessing
from ..config.models.models import PilgramFilter, SinglePictureDefinition
from ..mediaprocessing.processes import process_and_generate_collage
from .base import JobModelBase


class JobModelCollage(JobModelBase):
    def __init__(self, configuration_set: CollageConfigurationSet):
        super().__init__(configuration_set)
        self._media_type: MediaitemTypes = MediaitemTypes.collage

        self._ask_approval_each_capture = configuration_set.jobcontrol.ask_approval_each_capture
        self._total_captures_to_take = self._get_number_of_captures_from_merge_definition(configuration_set.processing.merge_definition)

        # self._validate_job()

    def get_phase1_singlepicturedefinition_per_index(self, index: int = None) -> SinglePictureDefinition:
        processing: CollageProcessing = self._configuration_set.processing
        # list only captured_images from merge_definition (excludes predefined)
        captured_images = [item for item in processing.merge_definition if not item.predefined_image]

        return SinglePictureDefinition(
            fill_background_enable=processing.capture_fill_background_enable,
            fill_background_color=processing.capture_fill_background_color,
            img_background_enable=processing.capture_img_background_enable,
            img_background_file=processing.capture_img_background_file,
            texts_enable=False,
            img_frame_enable=False,
            filter=captured_images[index].filter.value if index is not None else PilgramFilter.original.value,
        )

    def do_phase2_process_and_generate(self, phase1_mediaitems: list[V3Mediaitem], phase2_mediaitem: V3Mediaitem):
        process_and_generate_collage(phase1_mediaitems, phase2_mediaitem)
