"""
_summary_
"""
import json
import logging
import os
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from threading import Thread

from pymitter import EventEmitter
from statemachine import State, StateMachine

from ..appconfig import AppConfig
from .aquisitionservice import AquisitionService
from .mediacollectionservice import (
    PATH_ORIGINAL,
    MediacollectionService,
    MediaItem,
)

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
    thrilled = State()
    counting = State()
    capture_still = State()
    postprocess_still = State()
    copy_still = State()

    ## TRANSITIONS

    thrill = idle.to(thrilled)
    countdown = thrilled.to(counting)
    shoot = (
        idle.to(capture_still) | thrilled.to(capture_still) | counting.to(capture_still)
    )
    postprocess = capture_still.to(postprocess_still) | copy_still.to(postprocess_still)
    copy = capture_still.to(copy_still) | postprocess_still.to(copy_still)
    finalize = postprocess_still.to(idle) | copy_still.to(idle)

    _reset = (
        idle.to(idle)
        | thrilled.to(idle)
        | counting.to(idle)
        | capture_still.to(idle)
        | postprocess_still.to(idle)
        | copy_still.to(idle)
    )

    def __init__(
        self,
        evtbus: EventEmitter,
        config: AppConfig,
        aquisition_service: AquisitionService,
        mediacollection_service: MediacollectionService,
    ):
        self._evtbus: EventEmitter = evtbus
        self._config: AppConfig = config
        self._aquisition_service: AquisitionService = aquisition_service
        self._mediacollection_service: MediacollectionService = mediacollection_service

        self.timer: Thread = None
        self.timer_countdown = 0
        # filepath of the captured image that is processed in this run:
        self._filepath_originalimage_processing: str = None

        super().__init__()

        # register to send initial data SSE
        self._evtbus.on("publishSSE/initial", self._sse_initial_processinfo)

    # general on_ events
    def before_transition(self, event, state):
        """_summary_"""
        logger.info(f"Before '{event}', on the '{state.id}' state.")

    def on_transition(self, event, state):
        """_summary_"""
        logger.info(f"On '{event}', on the '{state.id}' state.")

    def on_exit_state(self, event, state):
        """_summary_"""
        logger.info(f"Exiting '{state.id}' state from '{event}' event.")

    def on_enter_state(self, event, state):
        """_summary_"""
        logger.info(f"Entering '{state.id}' state from '{event}' event.")

    def after_transition(self, event, state):
        """_summary_"""
        logger.info(f"After '{event}', on the '{state.id}' state.")

    ## specific on_ transition actions:

    def on_thrill(self):
        """_summary_"""
        self._evtbus.emit("statemachine/on_thrill")

    def on_shoot(self):
        """_summary_"""

    def on_postprocess(self):
        # create JPGs and add to db
        start_time_postproc = time.time()

        item: MediaItem = (
            self._mediacollection_service.create_imageset_from_originalimage(
                os.path.basename(self._filepath_originalimage_processing)
            )
        )

        _ = self._mediacollection_service.db_add_item(item)

        logger.info(f"capture {item=} successful")
        logger.info(
            f"post process time: {round((time.time() - start_time_postproc), 2)}s"
        )

        # to inform frontend about new image to display
        self._evtbus.emit(
            "publishSSE",
            sse_event="imagedb/newarrival",
            sse_data=json.dumps(item.asdict()),
        )

    def on_copy(self, filename: str = None):
        # also create a copy for photobooth compatibility
        if filename:
            # photobooth sends a complete path, where to put the file,
            # so copy it to requested filepath

            shutil.copy2(self._filepath_originalimage_processing, filename)

    ## specific on_state actions:

    def on_enter_idle(self):
        """_summary_"""
        # always remove old reference
        self._filepath_originalimage_processing = None

        # send 0 countdown to UI
        self._sse_processinfo(
            __class__.Stateinfo(
                state=self.current_state.id,
                countdown=0,
            )
        )

    def on_enter_counting(self):
        """_summary_"""
        self.timer_countdown = (
            self._config.common.PROCESS_COUNTDOWN_TIMER
            + self._config.common.PROCESS_COUNTDOWN_OFFSET
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

            if (
                self.timer_countdown <= self._config.common.PROCESS_COUNTDOWN_OFFSET
                and self.counting.is_active
            ):
                return

    def on_exit_counting(self):
        self.timer_countdown = 0

    def on_enter_capture_still(self):
        """_summary_"""
        self._evtbus.emit("statemachine/on_enter_capture_still")

        filepath_neworiginalfile = Path(
            PATH_ORIGINAL,
            f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S-%f')}.jpg",
        )
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
                self._filepath_originalimage_processing = filepath_neworiginalfile
            except TimeoutError:
                logger.error(
                    f"error capture image. timeout expired {attempt=}/{MAX_ATTEMPTS}, retrying"
                )
                # can we do additional error handling here?
            else:
                break
        else:
            # we failed finally all the attempts - deal with the consequences.
            logger.critical(
                "critical error capture image. "
                f"failed to get image after {MAX_ATTEMPTS} attempts. giving up!"
            )
            raise RuntimeError(
                f"finally failed after {MAX_ATTEMPTS} attempts to capture image!"
            )

        logger.info(
            f"capture still took time: {round((time.time() - start_time_capture), 2)}s"
        )

    def on_exit_capture_still(self):
        """_summary_"""
        self._evtbus.emit("statemachine/on_exit_capture_still")

    ### some external functions

    def evt_chose_1pic_get(self):
        logger.info("evt_chose_1pic_get called to take picture")
        if not self.idle.is_active:
            raise RuntimeError("bad request, only one request at a time!")

        self.thrill()
        self.countdown()
        self.shoot()
        self.postprocess()
        self.finalize()

    ### some custom helper

    def _sse_initial_processinfo(self):
        """_summary_"""
        self._sse_processinfo(__class__.Stateinfo(state=self.current_state.id))

    def _sse_processinfo(self, sse_data: Stateinfo):
        """_summary_"""
        self._evtbus.emit(
            "publishSSE",
            sse_event="statemachine/processinfo",
            sse_data=json.dumps(asdict(sse_data)),
        )
