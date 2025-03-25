import logging
from pathlib import Path
from uuid import uuid4

from statemachine import Event

from photobooth import PATH_PROCESSED, PATH_UNPROCESSED

from ...database.models import Mediaitem, MediaitemTypes
from ..aquisition import AquisitionService
from ..config.groups.actions import VideoConfigurationSet
from ..mediaprocessing.processes import process_video
from .base import Capture, CaptureSet, JobModelBase

logger = logging.getLogger(__name__)


class JobModelVideo(JobModelBase[VideoConfigurationSet]):
    def __init__(self, configuration_set: VideoConfigurationSet, aquisition_service: AquisitionService):
        super().__init__(configuration_set, MediaitemTypes.video, aquisition_service=aquisition_service)

        # self._validate_job()

    @property
    def total_captures_to_take(self) -> int:
        return 1

    def new_filename(self):
        return super().new_filename() + ".mp4"

    def on_enter_counting(self):
        self._aquisition_service.signalbackend_configure_optimized_for_video()

        super().on_enter_counting()

    def on_exit_counting(self):
        super().on_exit_counting()

    def on_enter_capture(self):
        video_file = self._aquisition_service.start_recording(video_framerate=self._configuration_set.processing.video_framerate)
        captureset = CaptureSet([Capture(video_file)])

        # add to tmp collection
        # update model so it knows the latest number of captures and the machine can react accordingly if finished
        self._capture_sets.append(captureset)

    def on_exit_capture(self):
        self._aquisition_service.stop_recording()  # blocks until video is written...

        logger.info(f"captureset {self._capture_sets} successful")

    def on_enter_approval(self): ...

    def on_exit_approval(self, event: Event): ...

    def on_enter_completed(self):
        # postprocess each video
        capture_to_process = self._capture_sets[0].captures[0].filepath
        logger.debug(f"recorded to {capture_to_process=}")

        original_filenamepath = self.new_filename()
        mediaitem = Mediaitem(
            id=uuid4(),
            job_identifier=self._job_identifier,
            media_type=self._media_type,
            unprocessed=Path(PATH_UNPROCESSED, original_filenamepath),
            processed=Path(PATH_PROCESSED, original_filenamepath),
            pipeline_config=self._configuration_set.processing.model_dump(mode="json"),
        )

        # apply video pipeline:
        process_video(capture_to_process, mediaitem)

        assert mediaitem.unprocessed.is_file()
        assert mediaitem.processed.is_file()

        # out to db/ui
        self.set_results(mediaitem, mediaitem.id)

        logger.info(f"capture {mediaitem=} successful")

    def on_exit_completed(self): ...

    def on_enter_finished(self): ...
