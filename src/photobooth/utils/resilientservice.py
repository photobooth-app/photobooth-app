import logging
import threading
import traceback
from abc import ABC, abstractmethod
from time import time

logger = logging.getLogger(__name__)


APP_PACKAGE = "photobooth"


class PermanentFault(Exception):
    """Raised from within the services when the service should not attempt recovery."""


class ServiceCrashedTemporarily(Exception):
    """Raised when the service probably only crashes temporarily and there is a chance to recover.
    can be raised from within service logic"""


class ServiceCrashedPermanently(Exception):
    """Raised when the service probably crashes permanently and will do so after a restart again.
    can be raised from within service logic"""


class CrashReporter(ABC):
    def __init__(self, service_name: str):
        self.service_name = service_name

    @abstractmethod
    def report(self, exc: Exception): ...


class VerboseCrashReporter(CrashReporter):
    def report(self, exc: Exception):
        tb = traceback.extract_tb(exc.__traceback__)
        origin = tb[1] if len(tb) > 1 else tb[0]
        logger.error(f"service {self.service_name} interrupted at {origin.filename}:{origin.lineno}, error: {exc}", exc_info=exc)


class QuietCrashReporter(CrashReporter):
    def report(self, exc: Exception):
        tb = traceback.extract_tb(exc.__traceback__)
        origin = tb[1] if len(tb) > 1 else tb[0]

        logger.info(f"service {self.service_name} interrupted at {origin.filename}:{origin.lineno}, error: {exc}")


class ResilientService(ABC):
    def __init__(
        self,
        retry_delay: int | float = 2,
        max_backoff: int | float = 20,
        crash_reporter: CrashReporter | None = None,
    ):
        super().__init__()
        self._lock = threading.Lock()
        self._started = False
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self._retry_delay = retry_delay
        self._max_backoff = max_backoff
        self._last_crash: float | None = None

        self._crash_reporter = crash_reporter or VerboseCrashReporter(self.__class__.__name__)

    # ---- Subclass Overrides ----
    @abstractmethod
    def setup_resource(self):
        """setup the resource right before run_service logic"""

    @abstractmethod
    def teardown_resource(self):
        """tear down the resource right after run_service logic and in case of crashes"""

    @abstractmethod
    def run_service(self):
        """service logic to be run when the service is started"""

    # ----------------------------

    def _report_crash(self, exc: Exception):
        self._crash_reporter.report(exc)

    def _run(self):
        attempt = 0
        while not self._stop_event.is_set():
            try:
                try:
                    self.setup_resource()
                except (AssertionError, PermanentFault) as e:  # assertion err is considered as programming bug or intended to be permanent fail.
                    self._report_crash(e)
                    raise ServiceCrashedPermanently(e) from e
                except Exception as e:
                    self._report_crash(e)
                    raise ServiceCrashedTemporarily(e) from e

                try:
                    logger.debug(f"{self}-resilient service start running service logic")
                    self._running = True
                    self.run_service()
                    self._running = False
                except (AssertionError, PermanentFault) as e:  # assertion err is considered as programming bug or intended to be permanent fail.
                    self._report_crash(e)

                    # if the run failed still try teardown to free up resources, but don't complain if it fails...
                    try:
                        self.teardown_resource()
                    except Exception as e2:
                        self._report_crash(e2)

                    raise ServiceCrashedPermanently(e) from e
                except Exception as e:
                    self._report_crash(e)

                    raise ServiceCrashedTemporarily(e) from e

                # if the run finished regular, in teardown
                try:
                    self.teardown_resource()
                except Exception as e:
                    self._report_crash(e)

                    raise ServiceCrashedTemporarily(e) from e

            except ServiceCrashedPermanently:
                logger.critical("Permanent failure detected. Stopping service and not trying to recover automatically. Check the error and restart.")
                self._running = False
                self._stop_event.set()
                break

            except ServiceCrashedTemporarily:
                self._running = False

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

            # returns the class info like <__main__.MyClass object at 0x...> or __str__ if defined in the class
            # the classes should therefore define a reasonable name and maybe additional information add there
            logger.debug(f"{self}-resilient service starting")

            self._stop_event.clear()
            self._thread = threading.Thread(name=self.__class__.__name__, target=self._run, daemon=True)
            self._thread.start()
            self._started = True

    def stop(self):
        with self._lock:
            if not self._started:
                return

            logger.debug(f"{self}-resilient service shutting down")

            assert self._thread
            self._stop_event.set()
            self._thread.join()
            self._started = False

    def recover(self):
        with self._lock:
            logger.warning(f"{self}-resilient service trying to recover")

            if not self._started:
                logger.warning("can only recover if service started previously")
                return

            if self._thread:
                self._stop_event.set()
                self._thread.join()

            self._stop_event.clear()
            self._thread = threading.Thread(name=self.__class__.__name__, target=self._run, daemon=True)
            self._thread.start()

    def is_started(self):
        # resource is only foreseen to start, Thread(run) might not have been called once yet, same for setup_resource.
        with self._lock:
            return self._started

    def is_running(self):
        # resource is setup (fully initialized) as capable to deliver, setup_resource has been called at least once.
        return self._running
