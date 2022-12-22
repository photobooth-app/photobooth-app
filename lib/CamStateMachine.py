# https://stackoverflow.com/questions/45321425/how-to-run-a-fsm-model-forever

import json
from threading import Thread, Lock
import time
from queue import Queue
from lib.ConfigSettings import settings
import logging

logger = logging.getLogger(__name__)


class TakePictureMachineModel(Thread):

    def __init__(self, ee):
        self._ee = ee  # eventemitter

        self.event_queue = Queue()
        self.lock = Lock()
        # has to be called whenever something inherits from Thread
        super(TakePictureMachineModel, self).__init__()

        # register to send initial data SSE
        self._ee.on("publishSSE/initial", self._publishSSEInitial)

    def invokeProcess(self, transition):

        if self.lock.locked():
            raise Exception("cannot trigger, only one process at a time!")

        # queue used to decouple requesting thread from this runner thread
        self.event_queue.put_nowait(transition)

    def abortProcess(self):
        # queue used to decouple requesting thread from this runner thread
        self.event_queue.put_nowait('abort')

    def run(self):
        # threaded runner, check consistently for new processes to start...
        while True:
            try:
                event = self.event_queue.get(timeout=1)
                logger.info(f"trigger event {event}")
                self.trigger(event)
            except:
                pass    # queue empty, ignore

    """
    STATE CALLBACKS
    """

    def on_enter_failsafe(self):
        logger.info(
            "trying to fix it... send event to client to reload, something like this?")
        # and go to idle
        self.trigger('recover')

    def on_enter_idle(self):
        self.lock.release()
        logger.debug("now UNlocked")
        logger.debug('waiting to start take pics!')

    def on_exit_idle(self):
        self.lock.acquire()
        logger.debug("now locked")

    def on_enter_armed(self):
        self._ee.emit("statemachine/armed")
        self.countdown()
        self.trigger('shoot')

    def on_enter_capture(self):
        self._ee.emit("statemachine/capture")
        self.trigger('finalize')

    def on_exit_capture(self):
        self._ee.emit("statemachine/finished")

    """
    some business logic
    """

    def _publishSSEInitial(self):
        self._publishSSE(
            "statemachine/processinfo", self.SSE_processinfo())

    def SSE_processinfo(self, additionalData={}):
        processinfo = {
            "state": self.state,
        }
        processinfo.update(additionalData)

        return processinfo

    def countdown(self):
        countdown = settings.common.PROCESS_COUNTDOWN_TIMER + \
            settings.common.PROCESS_COUNTDOWN_OFFSET
        while True:
            self._publishSSE(
                "statemachine/processinfo", self.SSE_processinfo({"countdown": round(countdown, 1)}))
            time.sleep(0.1)
            countdown -= 0.1
            if (countdown <= settings.common.PROCESS_COUNTDOWN_OFFSET):
                break

    """
    HELPER and OTHER stuff
    """

    def sse_emit_statechange(self):
        # set in machine to be called on every change
        self._publishSSE(
            "statemachine/processinfo", self.SSE_processinfo())

    def _publishSSE(self, sse_event, sse_data):
        self._ee.emit("publishSSE", sse_event=sse_event,
                      sse_data=json.dumps(sse_data))


states = [
    'idle',
    'armed',
    'capture',

    'failsafe',
]

"""
TRANSITIONS
"""
transitions = [
    # before: set_job(numberofpics)
    ['arm', ['idle', 'capture'], 'armed'],
    ['shoot', 'armed', 'capture'],
    ['finalize', 'capture', 'idle'],

    ['fails', '*', 'failsafe'],
    ['abort', '*', 'failsafe'],
    ['recover', 'failsafe', 'idle'],
]
