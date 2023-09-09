"""
_summary_
"""
import logging
import os
import time

from pymitter import EventEmitter
from statemachine import State, StateMachine

from ..appconfig import AppConfig, GroupMediaprocessingPipelineSingleImage
from ..utils.exceptions import ProcessMachineOccupiedError
from .aquisitionservice import AquisitionService
from .mediacollection.mediaitem import MediaItem, MediaItemTypes, get_new_filename
from .mediacollectionservice import (
    MediacollectionService,
)
from .mediaprocessingservice import MediaprocessingService
from .processing.jobmodels import JobModel
from .sseservice import SseEventDbInsert, SseEventProcessStateinfo

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


class ProcessingService(StateMachine):
    """
    use it:
        machine.thrill()
        machine.shoot()
    """

    ## STATES

    idle = State(initial=True)
    counting = State()
    capture = State()
    present_capture = State()
    job_postprocess = State()

    ## TRANSITIONS

    start = idle.to(counting)
    _counted = counting.to(capture)
    _captured = capture.to(present_capture)
    confirm = present_capture.to(counting, unless="took_all_captures") | present_capture.to(job_postprocess, cond="took_all_captures")
    reject = present_capture.to(counting)
    _finalize = job_postprocess.to(idle)
    _reset = idle.from_(idle, counting, capture, present_capture, job_postprocess)

    def __init__(
        self,
        evtbus: EventEmitter,
        config: AppConfig,
        aquisition_service: AquisitionService,
        mediacollection_service: MediacollectionService,
        mediaprocessing_service: MediaprocessingService,
    ):
        self._evtbus: EventEmitter = evtbus
        self._config: AppConfig = config
        self._aquisition_service: AquisitionService = aquisition_service
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._mediaprocessing_service: MediaprocessingService = mediaprocessing_service

        super().__init__(model=JobModel())

        # for proper linting
        self.model: JobModel

        # register to send initial data SSE
        self._evtbus.on("sse_dispatch_event/initial", lambda: self._evtbus.emit("sse_dispatch_event", SseEventProcessStateinfo(self.model)))

    ## transition actions

    def before_start(self, typ: JobModel.Typ, total_captures_to_take: int):
        assert isinstance(typ, JobModel.Typ)
        assert isinstance(total_captures_to_take, int)

        logger.info(f"set up job to start: {typ=}, {total_captures_to_take=}")

        self.model.start_model(typ, total_captures_to_take)

        logger.info(f"start job {self.model}")

    ## state actions

    def on_enter_state(self, event, state):
        """_summary_"""
        # logger.info(f"Entering '{state.id}' state from '{event}' event.")
        logger.info(f"on_enter_state {self.current_state.id=} ")

        # always send current state on enter so UI can react (display texts, wait message on postproc, ...)
        self._evtbus.emit("sse_dispatch_event", SseEventProcessStateinfo(self.model))

    def on_exit_idle(self):
        # when idle left, check that all is properly set up!

        if not self.model._validate_job():
            raise RuntimeError("job setup illegal")

    def on_enter_idle(self):
        """_summary_"""
        logger.info("state idle entered.")
        # reset old job data
        self.model.reset_job()

    def on_enter_counting(self):
        """_summary_"""
        # to prepare autofocus on backends and wled
        self._evtbus.emit("statemachine/on_thrill")

        # determine countdown time, first and following could have different times
        duration = (
            self._config.common.countdown_capture_first
            if (self.model.number_captures_taken() == 0)
            else self._config.common.countdown_capture_second_following
        )

        # if countdown is 0, skip following and transition to next state directy
        if duration == 0:
            logger.info("no timer, skip countdown")

            # leave this state by here
            self._counted()

        # starting countdown
        if (duration - self._config.common.countdown_camera_capture_offset) <= 0:
            logger.warning("duration equal/shorter than camera offset makes no sense. this results in 0s countdown!")

        logger.info(f"start countdown, duration_user={duration=}, offset_camera={self._config.common.countdown_camera_capture_offset}")
        self.model.start_countdown(
            duration_user=duration,
            offset_camera=self._config.common.countdown_camera_capture_offset,
        )
        # inform UI to count
        self._evtbus.emit("sse_dispatch_event", SseEventProcessStateinfo(self.model))

        # wait for countdown finished before continue machine
        self.model.wait_countdown_finished()  # blocking call

        # and now go on
        self._counted()

    def on_enter_capture(self):
        """_summary_"""
        logger.info(
            f"current capture ({self.model.number_captures_taken()+1}/{self.model.total_captures_to_take()}, "
            f"remaining {self.model.remaining_captures_to_take()-1})"
        )
        self._evtbus.emit("statemachine/on_enter_capture_still")

        filepath_neworiginalfile = get_new_filename(type=MediaItemTypes.IMAGE)
        logger.debug(f"capture to {filepath_neworiginalfile=}")

        start_time_capture = time.time()

        # at this point it's assumed, a HQ image was requested by statemachine.
        # seems to not make sense now, maybe revert hat...
        # waitforpic and store to disk
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                image_bytes = self._aquisition_service.wait_for_hq_image()

                with open(filepath_neworiginalfile, "wb") as file:
                    file.write(image_bytes)

                # populate image item for further processing:
                mediaitem = MediaItem(os.path.basename(filepath_neworiginalfile))
                self.model._last_captured_mediaitem = mediaitem

            except TimeoutError:
                logger.error(f"error capture image. timeout expired {attempt=}/{MAX_ATTEMPTS}, retrying")
                # can we do additional error handling here?
            else:
                break
        else:
            # we failed finally all the attempts - deal with the consequences.
            logger.critical(f"finally failed after {MAX_ATTEMPTS} attempts to capture image!")
            raise RuntimeError(f"finally failed after {MAX_ATTEMPTS} attempts to capture image!")

        logger.info(f"-- process time: {round((time.time() - start_time_capture), 2)}s to capture still")

        # capture finished, go to next state which is present. present also postprocesses capture.
        self._captured()

    def on_exit_capture(self):
        """_summary_"""
        self._evtbus.emit("statemachine/on_exit_capture_still")

        ## PHASE 1:
        # postprocess each capture individually
        logger.info("start postprocessing phase 1")

        # load last mediaitem for further processing
        mediaitem = self.model._last_captured_mediaitem
        logger.info(f"postprocessing last capture: {mediaitem=}")

        # always create unprocessed versions for later usage
        tms = time.time()
        mediaitem.create_fileset_unprocessed()
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create scaled images")

        # apply 1pic pipeline:
        tms = time.time()
        if self.model._typ == JobModel.Typ.image:
            self._mediaprocessing_service.process_singleimage(mediaitem, self._config.mediaprocessing_pipeline_singleimage)
        elif self.model._typ == JobModel.Typ.collage:
            # the captures in the context of a collage job can be processed differently:
            cfg_collage = self._config.mediaprocessing_pipeline_collage
            config_singleimage_captures_for_collage = GroupMediaprocessingPipelineSingleImage(
                pipeline_enable=True,  # for convenience this is always true now
                fill_background_enable=cfg_collage.capture_fill_background_enable,
                fill_background_color=cfg_collage.capture_fill_background_color,
                img_background_enable=cfg_collage.capture_img_background_enable,
                img_background_file=cfg_collage.capture_img_background_file,
                filter=cfg_collage.canvas_merge_definition[
                    self.model.number_captures_taken()
                ].filter.value,  # TODO: offset if predefined images! this is wrong!
            )

            self._mediaprocessing_service.process_singleimage(mediaitem, config_singleimage_captures_for_collage)

        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to process singleimage")

        assert mediaitem.fileset_valid()

        # add result to db
        # TODO: make configurable whether to hide pics that will be stitched to collage
        self.model.add_capture(self.model._last_captured_mediaitem)
        _ = self._mediacollection_service.db_add_item(mediaitem)

        logger.info(f"capture {mediaitem=} successful")

    def on_enter_present_capture(self):
        # get the last captured mediaitem for further processing
        last_captured_mediaitem = self.model._last_captured_mediaitem

        # if job is collage, each single capture could be confirmed or not:
        if self.model._typ == JobModel.Typ.collage:
            if self._config.common.collage_automatic_capture_continue:
                # auto continue with next countdown
                self._evtbus.emit("sse_dispatch_event", SseEventDbInsert(mediaitem=last_captured_mediaitem, present=False))
                self.confirm_capture()
            else:
                # present capture with buttons to approve.
                logger.info("finished capture, present to user to confirm or start over")
                self._evtbus.emit("sse_dispatch_event", SseEventDbInsert(mediaitem=last_captured_mediaitem, present=True, to_confirm_or_reject=True))

        elif self.model._typ == JobModel.Typ.image:
            # if not collage, we do not support approval screen - just continue.
            self.confirm_capture()

        else:
            raise RuntimeError(f"illegal job type {self.model._typ}")

    def on_exit_present_capture(self, event):
        if event == self.reject.name:
            delete_mediaitem = self.model._captures.pop()
            logger.info(f"rejected: {delete_mediaitem=}")

            self._mediacollection_service.delete_image_by_id(delete_mediaitem.id)
            self.model._last_captured_mediaitem = None

    def on_enter_job_postprocess(self):
        ## PHASE 2:
        # postprocess job as whole, create collage of single images, ...
        logger.info("start postprocessing phase 2")

        if self.model._typ == JobModel.Typ.collage:
            # apply 1pic pipeline:
            tms = time.time()
            mediaitem = self._mediaprocessing_service.process_collage(self.model._captures)
            logger.info(f"-- process time: {round((time.time() - tms), 2)}s to apply pipeline")

            # add collage to mediadb
            _ = self._mediacollection_service.db_add_item(mediaitem)

        else:
            mediaitem = self.model._last_captured_mediaitem

        ## FINISH:
        # to inform frontend about new image to display
        logger.info("finished job")

        # finally display end result to the user.
        self._evtbus.emit("sse_dispatch_event", SseEventDbInsert(mediaitem=mediaitem, present=True))

        # send machine to idle again
        self._finalize()

    def on_before_reset(self):
        print("TODO: remove all images that were captured by now")
        print("TODO: keep frontend in sync")

    def _check_occupied(self):
        if not self.idle.is_active:
            raise ProcessMachineOccupiedError("bad request, only one request at a time!")

    ### external functions to start processes

    def start_job_1pic(self):
        self._check_occupied()
        try:
            self.start(JobModel.Typ.image, 1)
        except Exception as exc:
            logger.exception(exc)
            self._reset()
            raise RuntimeError(f"error processing the job :| {exc}") from exc

    def start_job_collage(self):
        self._check_occupied()
        try:
            self.start(JobModel.Typ.collage, self._mediaprocessing_service.number_of_captures_to_take_for_collage())
        except Exception as exc:
            logger.exception(exc)
            self._reset()
            raise RuntimeError(f"error processing the job :| {exc}") from exc

    def start_job_video(self):
        raise NotImplementedError

    def job_finished(self):
        return self.idle.is_active

    def confirm_capture(self):
        self.confirm()

    def reject_capture(self):
        self.reject()

    def abort_process(self):
        self._reset()
