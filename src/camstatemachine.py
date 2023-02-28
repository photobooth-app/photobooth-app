"""
CamStateMachine
Controlling the process to take a picture/video, ...
https://stackoverflow.com/questions/45321425/how-to-run-a-fsm-model-forever
"""


import json
import logging
import time
from threading import Thread, Lock
from queue import Queue
from src.configsettings import settings

logger = logging.getLogger(__name__)


class TakePictureMachineModel(Thread):
    """_summary_

    Args:
        Thread (_type_): _description_
    """

    def __init__(self, ee):
        self._ee = ee  # eventemitter

        self.event_queue = Queue()
        self.lock = Lock()
        # has to be called whenever something inherits from Thread
        super(TakePictureMachineModel, self).__init__(daemon=True)

        # register to send initial data SSE
        self._ee.on("publishSSE/initial", self._publishSSEInitial)

    def invokeProcess(self, transition):
        """_summary_

        Args:
            transition (_type_): _description_

        Raises:
            RuntimeError: _description_
        """
        if self.lock.locked():
            raise RuntimeError("cannot trigger, only one process at a time!")

        # queue used to decouple requesting thread from this runner thread
        self.event_queue.put_nowait(transition)

    def abortProcess(self):
        """_summary_"""
        # queue used to decouple requesting thread from this runner thread
        self.event_queue.put_nowait("abort")

    def run(self):
        """_summary_"""
        # threaded runner, check consistently for new processes to start...
        while True:
            try:
                event = self.event_queue.get(timeout=1)
                logger.info(f"trigger event {event}")
                self.trigger(event)
            except:
                pass  # queue empty, ignore

    """
    STATE CALLBACKS
    """

    def on_enter_failsafe(self):
        """_summary_"""
        logger.info(
            "trying to fix it... send event to client to reload, something like this?"
        )
        # and go to idle
        self.trigger("recover")

    def on_enter_idle(self):
        """_summary_"""
        self.lock.release()
        logger.debug("now UNlocked")
        logger.debug("waiting to start take pics!")

    def on_exit_idle(self):
        """_summary_"""
        self.lock.acquire()
        logger.debug("now locked")

    def on_enter_armed(self):
        """_summary_"""
        self._ee.emit("statemachine/armed")
        self.countdown()
        self.trigger("shoot")

    def on_enter_capture(self):
        """_summary_"""
        self._ee.emit("statemachine/capture")
        self.trigger("finalize")

    def on_exit_capture(self):
        """_summary_"""
        self._ee.emit("statemachine/finished")

    """
    some business logic
    """

    def _publishSSEInitial(self):
        """_summary_"""
        self._publishSSE("statemachine/processinfo", self.SSE_processinfo())

    def SSE_processinfo(self, additionalData={}):
        """_summary_

        Args:
            additionalData (dict, optional): _description_. Defaults to {}.

        Returns:
            _type_: _description_
        """
        processinfo = {
            "state": self.state,
        }
        processinfo.update(additionalData)

        return processinfo

    def countdown(self):
        """_summary_"""
        countdown = (
            settings.common.PROCESS_COUNTDOWN_TIMER
            + settings.common.PROCESS_COUNTDOWN_OFFSET
        )
        while True:
            self._publishSSE(
                "statemachine/processinfo",
                self.SSE_processinfo({"countdown": round(countdown, 1)}),
            )
            time.sleep(0.1)
            countdown -= 0.1
            if countdown <= settings.common.PROCESS_COUNTDOWN_OFFSET:
                break

    """
    HELPER and OTHER stuff
    """

    def sse_emit_statechange(self):
        """_summary_"""
        # set in machine to be called on every change
        self._publishSSE("statemachine/processinfo", self.SSE_processinfo())

    def _publishSSE(self, sse_event, sse_data):
        self._ee.emit("publishSSE", sse_event=sse_event, sse_data=json.dumps(sse_data))


states = [
    "idle",
    "armed",
    "capture",
    "failsafe",
]

"""
TRANSITIONS
"""
transitions = [
    # before: set_job(numberofpics)
    ["arm", ["idle", "capture"], "armed"],
    ["shoot", "armed", "capture"],
    ["finalize", "capture", "idle"],
    ["fails", "*", "failsafe"],
    ["abort", "*", "failsafe"],
    ["recover", "failsafe", "idle"],
]
