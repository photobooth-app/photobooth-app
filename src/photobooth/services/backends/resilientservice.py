import logging
import threading
import time
import traceback
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ResilientService(ABC):
    def __init__(self, retry_delay=2, max_backoff=20, on_crash=None, max_start_attempts=None):
        self._lock = threading.Lock()
        self._started = False
        self._thread = None
        self._stop_event = threading.Event()
        self._retry_delay = retry_delay
        self._max_backoff = max_backoff
        self._on_crash = on_crash
        self._max_start_attempts = max_start_attempts

    # ---- Subclass Overrides ----
    @abstractmethod
    def setup_resource(self):
        pass

    @abstractmethod
    def teardown_resource(self):
        pass

    @abstractmethod
    def run_service(self):
        pass

    # ----------------------------

    def _report_crash(self, exc):
        tb = traceback.format_exc()
        logger.exception(exc)
        logger.critical(f"backend crashed, error: {exc}")

        if self._on_crash:
            try:
                self._on_crash(exc, tb)
            except Exception as hook_exc:
                logger.error(f"crash hook failed, error: {hook_exc}")

    def _backoff_delay(self, attempt):
        return min(self._retry_delay * (2 ** (attempt - 1)), self._max_backoff)

    def _try_with_retries(self, action):
        attempt = 0
        while not self._stop_event.is_set():
            try:
                action()
                return True
            except Exception as e:
                attempt += 1
                self._report_crash(e)

                if self._max_start_attempts and attempt >= self._max_start_attempts:
                    logger.error(f"service {str(action)} failed after {attempt} attempts.")
                    return False

                delay = self._backoff_delay(attempt)
                logger.info(f"service {str(action)} failed (attempt {attempt}). Retrying in {delay}s...")
                # wait up to delay seconds but in smaller increments so if service is stopped,
                # break out of the sleep loop. since .stopped is true, the outer while is also left.
                for _ in range(int(delay / 0.2)):
                    time.sleep(0.2)
                    if self._stop_event.is_set():
                        break
        return False

    def _run(self):
        loop_attempt = 0
        while not self._stop_event.is_set():
            if not self._try_with_retries(self.setup_resource):
                break

            try:
                self.run_service()
            except Exception as e:
                self._report_crash(e)

            try:
                self.teardown_resource()
            except Exception as e:
                self._report_crash(e)

            if self._stop_event.is_set():
                break

            loop_attempt += 1
            delay = self._backoff_delay(loop_attempt)
            logger.info(f"Restarting service loop attempt {loop_attempt} in {delay}s...")
            self._stop_event.clear()

            # wait up to delay seconds but in smaller increments so if service is stopped,
            # break out of the sleep loop. since .stopped is true, the outer while is also left.
            for _ in range(int(delay / 0.2)):
                time.sleep(0.2)
                if self._stop_event.is_set():
                    break

    def start(self):
        logger.debug(f"{self.__module__} start called")
        with self._lock:
            if self._started:
                logger.info("service already started.")
                return
            logger.info("launching service.")

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            self._started = True

    def stop(self):
        logger.debug(f"{self.__module__} stop called")
        with self._lock:
            if not self._started:
                logger.info("service not running.")
                return

            assert self._thread
            logger.info("shutting down service.")
            self._stop_event.set()
            self._thread.join()
            self._started = False

    def restart(self):
        logger.info("Restarting service...")

        self.stop()
        self.start()

    def is_running(self):
        with self._lock:
            return self._started
