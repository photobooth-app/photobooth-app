import time
from threading import Condition, Thread


class CountdownTimer:
    TIMER_TICK = 0.1
    TIMER_TOLERANCE = TIMER_TICK / 2  # to account for float not 100% accurate

    def __init__(self):
        self._duration: float = 0
        self._countdown: float = 0

        self._ticker_thread: Thread | None = None
        self._finished_condition: Condition = Condition()

    def start(self, duration: float):
        self._duration = duration
        self._countdown = duration

        if self._countdown_finished():
            # countdown on start already finished because initialized with 0 duration.
            # no need to start a thread, exit early to continue as fast as possible with job.
            return

        self._ticker_thread = Thread(name="_countdowntimer_thread", target=self._countdowntimer_fun, daemon=True)
        self._ticker_thread.start()

    def reset(self):
        self._duration = 0
        self._countdown = 0

    def wait_countdown_finished(self):
        # return early if already finished when called.
        # to avoid any race condition if countdown from 0 but wait_countdown was not called yet so condition is missed.
        if self._countdown_finished():
            return

        with self._finished_condition:
            if not self._finished_condition.wait(timeout=(self._duration + 1)):
                raise TimeoutError("error timing out")

    def _countdown_finished(self):
        return self._countdown <= self.TIMER_TOLERANCE

    def _countdowntimer_fun(self):
        while not self._countdown_finished():
            time.sleep(self.TIMER_TICK)

            self._countdown -= self.TIMER_TICK

        # ticker finished, reset
        self.reset()

        # notify waiting threads
        with self._finished_condition:
            self._finished_condition.notify_all()

        # done, exit fun, exit thread
