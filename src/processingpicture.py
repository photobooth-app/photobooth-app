"""
_summary_
"""
import json
import logging
import time
from dataclasses import dataclass, asdict
from threading import Thread
from pymitter import EventEmitter
from statemachine import StateMachine, State
from src.configsettings import settings

logger = logging.getLogger(__name__)


# use it:
# machine.arm()
# machine.shoot()


class ProcessingPicture(StateMachine):
    """_summary_"""

    idle = State("Initial", initial=True)
    countdown = State("Countdown")
    capture_still = State("Capture Still")
    final = State("Final")

    arm = idle.to(countdown)
    shoot = countdown.to(capture_still) | idle.to(capture_still)
    finalize = capture_still.to(final)

    @dataclass
    class Stateinfo:
        """_summary_"""

        state: str
        countdown: float = 0

    def __init__(self, evtbus):
        self._evtbus: EventEmitter = evtbus  # eventemitter

        self.timer = Thread(
            name="_decrease_countdown",
            target=self._decrease_countdown,
            daemon=True,
        )
        self.timer_countdown = 0

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

    # specific state on_ events

    def on_arm(self):
        """_summary_"""
        self._evtbus.emit("statemachine/armed")

    def on_enter_countdown(self):
        """_summary_"""
        self.timer_countdown = (
            settings.common.PROCESS_COUNTDOWN_TIMER
            + settings.common.PROCESS_COUNTDOWN_OFFSET
        )
        logger.info(f"loaded timer_countdown='{self.timer_countdown}'")
        logger.info("starting timer")
        self.timer.start()

    def on_exit_countdown(self):
        """_summary_"""
        # send 0 countdown to UI
        self._sse_processinfo(
            ProcessingPicture.Stateinfo(
                state=self.current_state.id,
                countdown=0,
            )
        )

    def on_enter_capture_still(self):
        """_summary_"""
        self._evtbus.emit("statemachine/capture")

        self.finalize()

    def on_exit_capture_still(self):
        """_summary_"""
        self._evtbus.emit("statemachine/finished")

    ### some external functions
    # none yet

    ### some custom helper

    def _decrease_countdown(self):
        """_summary_"""
        while self.timer_countdown >= settings.common.PROCESS_COUNTDOWN_OFFSET:
            self._sse_processinfo(
                ProcessingPicture.Stateinfo(
                    state=self.current_state.id,
                    countdown=round(self.timer_countdown, 1),
                )
            )
            time.sleep(0.1)
            self.timer_countdown -= 0.1

        self.shoot()

    def _sse_initial_processinfo(self):
        """_summary_"""
        self._sse_processinfo(ProcessingPicture.Stateinfo(state=self.current_state.id))

    def _sse_processinfo(self, sse_data: Stateinfo):
        """_summary_"""
        self._evtbus.emit(
            "publishSSE",
            sse_event="statemachine/processinfo",
            sse_data=json.dumps(asdict(sse_data)),
        )
