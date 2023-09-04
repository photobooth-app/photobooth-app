"""
Handle all media collection related functions
"""
import subprocess
import time

from pymitter import EventEmitter

from ..appconfig import AppConfig
from .baseservice import BaseService
from .mediacollection.mediaitem import MediaItem
from .mediacollectionservice import MediacollectionService

TIMEOUT_PROCESS_RUN = 6  # command to print needs to complete within 6 seconds.


class PrintingService(BaseService):
    """Handle all image related stuff"""

    def __init__(self, evtbus: EventEmitter, config: AppConfig, mediacollection_service: MediacollectionService):
        super().__init__(evtbus=evtbus, config=config)

        # common objects
        self._mediacollection_service: MediacollectionService = mediacollection_service

        # custom service objects
        self._last_print_time = None
        self._printing_queue = None  # TODO: could add queue later

    def print(self, mediaitem: MediaItem):
        ## print mediaitem

        if not self._config.hardwareinputoutput.printing_enabled:
            raise ConnectionRefusedError("Printing is disabled! Enable in config first.")

        # block queue new prints until configured time is over
        if self.is_blocked():
            raise BlockingIOError(f"Print request ignored! Wait {self.remaining_time_blocked():.0f}s before try again.")

        # filename absolute to print, use in printing command
        filename = mediaitem.path_full.absolute()

        try:
            # print command
            self._logger.info(f"printing {filename=}")

            completed_process = subprocess.run(
                str(self._config.hardwareinputoutput.printing_command).format(filename=filename),
                capture_output=True,
                check=True,
                timeout=TIMEOUT_PROCESS_RUN,
                shell=True,  # needs to be shell so a string as command is accepted.
            )

            self._logger.info(f"cmd={completed_process.args}")
            self._logger.info(f"stdout={completed_process.stdout}")
            self._logger.debug(f"stderr={completed_process.stderr}")

            self._logger.info(f"print command started successfully {mediaitem}")

            # update last print time to calc block time on next run
            self._start_time_blocked()
        except Exception as exc:
            raise RuntimeError(f"print failed, error {exc}") from exc

    def is_blocked(self):
        return self.remaining_time_blocked() > 0.0

    def remaining_time_blocked(self) -> float:
        if self._last_print_time is None:
            return 0.0

        delta = time.time() - self._last_print_time
        if delta >= self._config.hardwareinputoutput.printing_blocked_time:
            # last print is longer than configured time in the past - return 0 to indicate no wait time
            return 0.0
        else:
            # there is some time to wait left.
            return self._config.hardwareinputoutput.printing_blocked_time - delta

    def _start_time_blocked(self):
        self._last_print_time = time.time()

        # TODO: add some timer/coroutine to send regular update to UI with current remaining time blocked

    def _print_timer_fun(self):
        ## thread to send updates to client about remaining blocked time
        pass
