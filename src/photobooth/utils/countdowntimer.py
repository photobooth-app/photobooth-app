import logging
import threading
import time

logger = logging.getLogger("counter")


class CountdownTimer:
    def __init__(self):
        self._lock = threading.Lock()
        self._done_event = threading.Event()
        self._thread = None
        self._timer = None
        self._running = False

        self._duration: float = 0.0

    def start(self, duration: float):
        with self._lock:
            if self._running:
                raise RuntimeError("Countdown already running.")

            self._done_event.clear()
            self._running = True
            self._duration = duration

            logger.warning(time.perf_counter())
            self._timer = threading.Timer(duration, self._countdown_finished)
            self._timer.start()
            logger.warning(time.perf_counter())

    def _countdown_finished(self):
        logger.warning(time.perf_counter())
        with self._lock:
            self._running = False
            self._duration = 0.0
            self._done_event.set()

    # def _run_countdown(self):
    #     logger.warning(time.perf_counter())
    #     time.sleep(self._duration)

    #     logger.warning(time.perf_counter())

    #     with self._lock:
    #         self._running = False
    #         self._duration = 0.0
    #         self._done_event.set()

    def wait_countdown_finished(self):
        self._done_event.wait()

        logger.warning(time.perf_counter())

    def is_running(self):
        with self._lock:
            return self._running
