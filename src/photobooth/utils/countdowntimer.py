import threading
import time


class CountdownTimer:
    def __init__(self):
        self._lock = threading.Lock()
        self._done_event = threading.Event()
        self._thread = None
        self._running = False

        self._duration: float = 0.0

    def start(self, duration: float):
        with self._lock:
            if self._running:
                raise RuntimeError("Countdown already running.")

            self._done_event.clear()
            self._running = True
            self._duration = duration

            self._thread = threading.Thread(target=self._run_countdown, daemon=True)
            self._thread.start()

    def _run_countdown(self):
        end_time = time.monotonic() + self._duration
        while True:
            remaining = end_time - time.monotonic()
            if remaining <= 0:
                break

            time.sleep(min(0.05, remaining))

        with self._lock:
            self._running = False
            self._duration = 0.0
            self._done_event.set()

    def wait_countdown_finished(self):
        self._done_event.wait()

    def is_running(self):
        with self._lock:
            return self._running
