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
from .processing.jobmodels import JobModelBase

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

        super().__init__(model=JobModelBase())

        # register to send initial data SSE
        self._evtbus.on("publishSSE/initial", self._sse_initial_processinfo)

    ## transition actions

    def before_start(self, typ: JobModelBase.Typ, total_captures_to_take: int):
        assert isinstance(typ, JobModelBase.Typ)
        assert isinstance(total_captures_to_take, int)

        logger.info(f"set up job to start: {typ=}, {total_captures_to_take=}")

        self.model: JobModelBase  # for linting
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

        # self._evtbus.emit("statemachine/on_thrill")
        # TODO: set backend to capture mode

        self.timer_countdown = (
            self._config.common.PROCESS_COUNTDOWN_TIMER + self._config.common.PROCESS_COUNTDOWN_OFFSET
        )
        logger.info(f"loaded timer_countdown='{self.timer_countdown}'")
        logger.info("starting timer")

        while self.timer_countdown > 0:
            self._sse_processinfo(
                __class__.Stateinfo(
                    state=self.current_state.id,
                    countdown=round(self.timer_countdown, 1),
                )
            )
            time.sleep(0.1)
            self.timer_countdown -= 0.1

            if self.timer_countdown <= self._config.common.PROCESS_COUNTDOWN_OFFSET and self.counting.is_active:
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
            f"current capture ({self.model.number_captures_taken()+1}/{self.model.total_captures_to_take()}, remain {self.model.remaining_captures_to_take()-1})"
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

        if self.model.took_all_captures():
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
            self._mediaprocessing_service.create_scaled_unprocessed_repr(mediaitem)
            logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create scaled images")

            # apply 1pic pipeline:
            tms = time.time()
            self._mediaprocessing_service.apply_pipeline_1pic(mediaitem)
            logger.info(f"-- process time: {round((time.time() - tms), 2)}s to apply pipeline")

            # add result to db
            _ = self._mediacollection_service.db_add_item(mediaitem)

            mediaitems.append(mediaitem)
            logger.info(f"capture {mediaitem=} successful")

        ## PHASE 2:
        # postprocess job as whole, create collage of single images, ...
        logger.info("start postprocessing phase 2")

        #
        if self.model._typ == JobModelBase.Typ.collage:
            # apply 1pic pipeline:
            tms = time.time()
            mediaitem = self._mediaprocessing_service.apply_pipeline_collage(mediaitems)
            logger.info(f"-- process time: {round((time.time() - tms), 2)}s to apply pipeline")

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

    ### some external functions

    def evt_chose_1pic_get(self):
        logger.info("evt_chose_1pic_get called to take picture")
        if not self.idle.is_active:
            raise ProcessMachineOccupiedError("bad request, only one request at a time!")

        try:
            self.start(JobModelBase.Typ.image, 1)

        except Exception as exc:
            logger.exception(exc)
            logger.critical(f"something went wrong :( {exc}")
            self._reset()
            raise RuntimeError(f"something went wrong :( {exc}") from exc

    def evt_chose_collage_get(self):
        logger.info("evt_chose_collage_get called to take collage")
        if not self.idle.is_active:
            raise ProcessMachineOccupiedError("bad request, only one request at a time!")

        try:
            self.start(JobModelBase.Typ.collage, 3)
            # if autocontinue:
            self.capture_next()
            self.capture_next()

        except Exception as exc:
            logger.exception(exc)
            logger.critical(f"something went wrong :( {exc}")
            self._reset()
            raise RuntimeError(f"something went wrong :( {exc}") from exc

    def evt_chose_video_get(self):
        logger.info("evt_chose_video_get called to take collage")
        if not self.idle.is_active:
            raise ProcessMachineOccupiedError("bad request, only one request at a time!")

        try:
            self.start()  # TODO: add job here?
            self.capture_next()

        except Exception as exc:
            logger.exception(exc)
            logger.critical(f"something went wrong :( {exc}")
            self._reset()
            raise RuntimeError(f"something went wrong :( {exc}") from exc

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
