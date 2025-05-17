import logging
import threading
from abc import ABC, abstractmethod
from time import time

logger = logging.getLogger(__name__)


class ServiceCrashed(Exception): ...


class ResilientService(ABC):
    def __init__(self, retry_delay: int | float = 2, max_backoff: int | float = 20):
        self._lock = threading.Lock()
        self._started = False
        self._thread = None
        self._stop_event = threading.Event()
        self._retry_delay = retry_delay
        self._max_backoff = max_backoff
        self._last_crash: float | None = None

    # ---- Subclass Overrides ----
    @abstractmethod
    def setup_resource(self): ...

    @abstractmethod
    def teardown_resource(self): ...

    @abstractmethod
    def run_service(self): ...

    # ----------------------------

    def _report_crash(self, exc: Exception):
        logger.exception(exc)
        logger.critical(f"normal service op interrupted, error: {exc}")

    def _run(self):
        attempt = 0
        while not self._stop_event.is_set():
            try:
                try:
                    self.setup_resource()
                except Exception as e:
                    self._report_crash(e)

                    raise ServiceCrashed(e) from e

                try:
                    logger.info(f"{self.__class__.__name__}-resilient service start running service logic")
                    self.run_service()
                except Exception as e:
                    self._report_crash(e)

                    # if the run failed, some last resort teardown here...
                    try:
                        self.teardown_resource()
                    except Exception as e2:
                        logger.critical(f"teardown resource after run failed errored also: {e2}")

                    raise ServiceCrashed(e) from e

                try:
                    self.teardown_resource()
                except Exception as e:
                    self._report_crash(e)

            except ServiceCrashed:
                if self._stop_event.is_set():
                    break

                logger.info("trying to recover from service interruption")

                if self._last_crash and ((time() - self._last_crash) > (self._max_backoff + 2)):
                    logger.info("reset attempt to 0 because last_crash is longer ago than max_backoff")
                    attempt = 0

                self._last_crash = time()
                attempt += 1
                delay = min(self._retry_delay * (2 ** (attempt - 1)), self._max_backoff)
                logger.warning(f"normal service operation failed (attempt {attempt}). Retrying in {delay}s...")

                # wait up to delay seconds but if service is stopped,
                # the wait returns and the loop will exit because it also checks for the stop_event
                self._stop_event.wait(timeout=delay)

    def start(self):
        with self._lock:
            if self._started:
                return

            logger.debug(f"{self.__class__.__name__}-resilient service starting")

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            self._started = True

    def stop(self):
        with self._lock:
            if not self._started:
                return

            logger.debug(f"{self.__class__.__name__}-resilient service shutting down")

            assert self._thread
            self._stop_event.set()
            self._thread.join()
            self._started = False

    def restart(self):
        logger.info(f"{self.__class__.__name__}-resilient service restarting")

        self.stop()
        self.start()

    def is_running(self):
        with self._lock:
            return self._started
