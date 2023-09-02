"""
_summary_
"""
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
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
    job_postprocess = State()

    ## TRANSITIONS

    start = idle.to(counting)
    capture_next = (
        # idle.to(capture)
        counting.to(capture)
        | capture.to(counting, unless="took_all_captures")
        | capture.to(job_postprocess, cond="took_all_captures")
    )
    # capture_repeat=
    _postprocess = capture.to(job_postprocess)
    _finalize = job_postprocess.to(idle)
    _reset = idle.to(idle) | counting.to(idle) | capture.to(idle) | job_postprocess.to(idle)

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
        logger.info("state counting entered")

        self._evtbus.emit("statemachine/on_thrill")
        # TODO: set backend to capture mode

        # determine countdown time
        self.timer_countdown = 0.0
        self.timer_countdown += (
            self._config.common.countdown_capture_first
            if (self.model.number_captures_taken() == 0)
            else self._config.common.countdown_capture_second_following
        )

        logger.info(f"loaded '{self.timer_countdown=}'")

        if self.timer_countdown == 0:
            logger.info("no timer, skip countdown")
            self.capture_next()

        logger.info("starting timer")

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
                self.capture_next()
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
                self.model.add_capture(Path(filepath_neworiginalfile))
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

        if not self.model.took_all_captures():
            if self._config.common.collage_automatic_capture_continue:
                self.continue_job()
            else:
                logger.info("finished capture, present to user to confirm or start over")
                self._evtbus.emit(
                    "publishSSE",
                    sse_event="imagedb/newarrival",
                    sse_data="",  # TODO: need to postprocess capture phase 1 earlier now! json.dumps(mediaitem.asdict()),
                )

        if self.model.took_all_captures():
            # last image taken, automatic continue
            # enhancement: make configurable and let user choose to repeat capture or confirm to continue
            logger.info(f"took_all_captures ({self.model.number_captures_taken()=}) _finalize now")
            self._postprocess()

    def on_exit_capture(self):
        """_summary_"""
        logger.info("on_exit_capture_still")
        self._evtbus.emit("statemachine/on_exit_capture_still")

    def on_enter_job_postprocess(self):
        ## PHASE 1:
        # postprocess each capture individually
        logger.info("start postprocessing phase 1")
        mediaitems: list[MediaItem] = []
        for index, capture in enumerate(self.model._captures):
            logger.info(f"postprocessing no {index+1}: {capture}")

            ## following is the former code:
            # create mediaitem for further processing
            mediaitem = MediaItem(os.path.basename(capture))

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
            _ = self._mediacollection_service.db_add_item(mediaitem)

            mediaitems.append(mediaitem)
            logger.info(f"capture {mediaitem=} successful")

        ## PHASE 2:
        # postprocess job as whole, create collage of single images, ...
        logger.info("start postprocessing phase 2")

        if self.model._typ == JobModel.Typ.collage:
            # apply 1pic pipeline:
            tms = time.time()
            mediaitem = self._mediaprocessing_service.apply_pipeline_collage(mediaitems)
            logger.info(f"-- process time: {round((time.time() - tms), 2)}s to apply pipeline")

            # add collage to mediadb
            _ = self._mediacollection_service.db_add_item(mediaitem)

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

    def continue_job(self):
        self.capture_next()

    def repeat_last_capture(self):
        raise NotImplementedError
        # TODO:self.capture_repeat()

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
