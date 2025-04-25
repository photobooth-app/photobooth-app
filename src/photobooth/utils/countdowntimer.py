import logging
import threading

logger = logging.getLogger("counter")


class CountdownTimer:
    def __init__(self):
        self._lock = threading.Lock()
        self._done_event = threading.Event()
        self._timer: threading.Timer | None = None
        self._running: bool = False

        self._duration: float = 0.0

    def start(self, duration: float):
        with self._lock:
            if self._running:
                raise RuntimeError("Countdown already running.")

            self._done_event.clear()
            self._running = True
            self._duration = duration

            self._timer = threading.Timer(duration, self._countdown_finished)
            self._timer.start()

    def _countdown_finished(self):
        with self._lock:
            self._running = False
            self._duration = 0.0
            self._done_event.set()

    def wait_countdown_finished(self):
        self._done_event.wait()
