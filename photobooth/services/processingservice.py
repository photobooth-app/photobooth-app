"""
_summary_
"""
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from threading import Thread

from pymitter import EventEmitter
from statemachine import State, StateMachine

from ..appconfig import AppConfig
from ..utils.exceptions import ProcessMachineOccupiedError
from .aquisitionservice import AquisitionService
from .mediacollection.mediaitem import MediaItem, MediaItemTypes, get_new_filename
from .mediacollectionservice import (
    MediacollectionService,
)
from .mediaprocessingservice import MediaprocessingService
from .processing.jobmodels import JobModel

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


class ProcessingService(StateMachine):
    """
    use it:
        machine.thrill()
        machine.shoot()
    """

    @dataclass
    class Stateinfo:
        """_summary_"""

        state: str
        countdown: float = 0
        display_cheese: bool = False  # TODO: implement in frontend

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
    confirm = present_capture.to(counting, unless="took_all_captures") | present_capture.to(
        job_postprocess, cond="took_all_captures"
    )
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

        self.timer: Thread = None
        self.timer_countdown = 0

        super().__init__(model=JobModel())

        # register to send initial data SSE
        self._evtbus.on("publishSSE/initial", self._sse_initial_processinfo)

    ## transition actions

    def before_start(self, typ: JobModel.Typ, total_captures_to_take: int):
        assert isinstance(typ, JobModel.Typ)
        assert isinstance(total_captures_to_take, int)

        logger.info(f"set up job to start: {typ=}, {total_captures_to_take=}")

        self.model: JobModel  # for linting
        self.model.start_model(typ, total_captures_to_take)

        logger.info(f"start job {self.model}")

    ## state actions

    def on_enter_state(self, event, state):
        """_summary_"""
        # logger.info(f"Entering '{state.id}' state from '{event}' event.")
        logger.info(f"on_enter_state {self.current_state.id=} ")

        # always send current state on enter so UI can react (display texts, wait message on postproc, ...)
        self._sse_processinfo(
            __class__.Stateinfo(
                state=self.current_state.id,
                countdown=self.timer_countdown,
            )
        )

    def on_exit_idle(self):
        # when idle left, check that all is properly set up!

        if not self.model.validate_job():
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
        self.timer_countdown = 0.0
        self.timer_countdown += (
            self._config.common.countdown_capture_first
            if (self.model.number_captures_taken() == 0)
            else self._config.common.countdown_capture_second_following
        )

        # if countdown is 0, skip following and transition to next state directy
        if self.timer_countdown == 0:
            logger.info("no timer, skip countdown")
            self._counted()

        logger.info(f"starting timer {self.timer_countdown=}")

        while self.timer_countdown > 0:
            self._sse_processinfo(
                __class__.Stateinfo(
                    state=self.current_state.id,
                    countdown=round(self.timer_countdown, 1),
                    display_cheese=(
                        True if (self.timer_countdown <= self._config.common.countdown_cheese_message_offset) else False
                    ),
                )
            )
            time.sleep(0.1)
            self.timer_countdown -= 0.1

            if self.timer_countdown <= self._config.common.countdown_camera_capture_offset and self.counting.is_active:
                logger.info("going to next capture now")
                self._counted()
                break

    def on_exit_counting(self):
        logger.info("state counting exit")

        # TODO: replace by statemachineinfo class
        self.timer_countdown = 0

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

                # send 0 countdown to UI
                self._sse_processinfo(
                    __class__.Stateinfo(
                        state=self.current_state.id,
                        countdown=0,
                    )
                )

                with open(filepath_neworiginalfile, "wb") as file:
                    file.write(image_bytes)

                # populate image item for further processing:
                mediaitem = MediaItem(os.path.basename(filepath_neworiginalfile))
                self.model._last_capture = mediaitem

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
        logger.info("on_exit_capture_still")
        self._evtbus.emit("statemachine/on_exit_capture_still")

    def on_enter_present_capture(self):
        ## PHASE 1:
        # postprocess each capture individually
        logger.info("start postprocessing phase 1")

        # load last mediaitem for further processing
        mediaitem = self.model._last_capture
        logger.info(f"postprocessing last capture: {mediaitem=}")

        # always create unprocessed versions for later usage
        tms = time.time()
        mediaitem.create_fileset_unprocessed()
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create scaled images")

        # apply 1pic pipeline:
        tms = time.time()
        self._mediaprocessing_service.apply_pipeline_1pic(mediaitem)
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to apply pipeline")

        assert mediaitem.fileset_valid()

        # add result to db
        # TODO: make configurable whether to hide pics that will be stitched to collage
        self.model.add_capture(self.model._last_capture)
        _ = self._mediacollection_service.db_add_item(mediaitem)

        logger.info(f"capture {mediaitem=} successful")

        # if job is collage, each single capture could be confirmed or not:
        if self.model._typ == JobModel.Typ.collage:
            if self._config.common.collage_automatic_capture_continue:
                # auto continue with next countdown
                self.confirm_capture()
                # TODO: update the frontend gallery on delete/insert, with or without presenting!
            else:
                # present capture with buttons to approve.
                logger.info("finished capture, present to user to confirm or start over")
                self._evtbus.emit(
                    "publishSSE",
                    sse_event="imagedb/newarrival",
                    sse_data=json.dumps(mediaitem.asdict()),
                )
        else:
            # if not collage, there is single approval so -> confirm and continue
            self.confirm_capture()

    def on_exit_present_capture(self, event):
        if event == self.reject.name:
            delete_mediaitem = self.model._captures.pop()
            logger.info(f"rejected: {delete_mediaitem=}")

            self._mediacollection_service.delete_image_by_id(delete_mediaitem.id)
            self.model._last_capture = None

    def on_enter_job_postprocess(self):
        ## PHASE 2:
        # postprocess job as whole, create collage of single images, ...
        logger.info("start postprocessing phase 2")

        if self.model._typ == JobModel.Typ.collage:
            # apply 1pic pipeline:
            tms = time.time()
            mediaitem = self._mediaprocessing_service.apply_pipeline_collage(self.model._captures)
            logger.info(f"-- process time: {round((time.time() - tms), 2)}s to apply pipeline")

            # add collage to mediadb
            _ = self._mediacollection_service.db_add_item(mediaitem)
        else:
            mediaitem = self.model._last_capture

        ## FINISH:
        # to inform frontend about new image to display
        logger.info("finished job")
        self._evtbus.emit(
            "publishSSE",
            sse_event="imagedb/newarrival",
            sse_data=json.dumps(mediaitem.asdict()),
        )

        # send machine to idle again
        self._finalize()

    def on_before_reset(self):
        print("TODO: remove all images that were captured by now")

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
        self._check_occupied()
        self.start(JobModel.Typ.video, 1)

    def job_finished(self):
        return self.idle.is_active

    def confirm_capture(self):
        self.confirm()

    def reject_capture(self):
        self.reject()

    def abort_capture(self):
        self._reset()

    ### some custom helper

    def _sse_initial_processinfo(self):
        """_summary_"""
        self._sse_processinfo(__class__.Stateinfo(state=self.current_state.id))

    def _sse_processinfo(self, sse_data: str):
        """_summary_"""
        self._evtbus.emit(
            "publishSSE",
            sse_event="statemachine/processinfo",
            sse_data=json.dumps(asdict(sse_data)),
        )
