"""
Handle all media collection related functions
"""

import subprocess
import time

from .baseservice import BaseService
from .config import appconfig
from .informationservice import InformationService
from .mediacollection.mediaitem import MediaItem
from .mediacollectionservice import MediacollectionService
from .sseservice import SseEventFrontendNotification, SseService

TIMEOUT_PROCESS_RUN = 6  # command to print needs to complete within 6 seconds.


class ShareService(BaseService):
    """Handle all image related stuff"""

    def __init__(self, sse_service: SseService, mediacollection_service: MediacollectionService, information_service: InformationService):
        super().__init__(sse_service)

        # common objects
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._information_service: InformationService = information_service

        # custom service objects
        self._last_print_time = None
        self._last_printing_blocked_time = None
        self._printing_queue = None  # TODO: could add queue later

    def start(self):
        # unblock after restart immediately
        self._last_print_time = None

    def stop(self):
        pass

    def share(self, mediaitem: MediaItem, config_index: int = 0):
        """print mediaitem"""

        if not appconfig.share.sharing_enabled:
            self._sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="negative",
                    message="Share service is disabled! Enable in config first.",
                    caption="Share Service Error",
                )
            )
            raise ConnectionRefusedError("Share service is disabled! Enable in config first.")

        # get config
        try:
            action_config = appconfig.share.actions[config_index]
        except Exception as exc:
            self._logger.critical(f"could not find action configuration with index {config_index}, error {exc}")
            raise exc

        # check counter limit
        max_shares = getattr(action_config.processing, "max_shares", 0)
        limites = self._information_service._stats_counter.limites
        current_shares = 0
        if action_config.name in limites:
            current_shares = limites[action_config.name]
        if max_shares > 0 and current_shares >= max_shares:
            self._sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="negative",
                    message=f"{action_config.trigger.ui_trigger.title} quota exceeded ({max_shares} maximum)",
                    caption="Share/Print quota",
                )
            )
            raise BlockingIOError("Maximum number of Share/Print reached!")
        
        # block queue new prints until configured time is over
        if self.is_blocked():
            self._sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="info",
                    message=f"Share/Print request ignored! Wait {self.remaining_time_blocked():.0f}s before trying again.",
                    caption="Share Service Error",
                )
            )
            raise BlockingIOError(f"Share/Print request ignored! Wait {self.remaining_time_blocked():.0f}s before trying again.")

        # filename absolute to print, use in printing command
        filename = mediaitem.path_full.absolute()

        try:
            # print command
            self._logger.info(f"share/print {filename=}")

            completed_process = subprocess.run(
                str(action_config.processing.share_command).format(filename=filename),
                capture_output=True,
                check=True,
                timeout=TIMEOUT_PROCESS_RUN,
                shell=True,  # needs to be shell so a string as command is accepted.
            )

            self._logger.info(f"cmd={completed_process.args}")
            self._logger.info(f"stdout={completed_process.stdout}")
            self._logger.debug(f"stderr={completed_process.stderr}")

            self._logger.info(f"command started successfully {mediaitem}")

            self._sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="positive",
                    message=f"Process '{action_config.name}' started...",
                    caption="Share Service",
                    spinner=True,
                )
            )

            # update last print time to calc block time on next run
            self._start_time_blocked(action_config.processing.share_blocked_time)
        except Exception as exc:
            self._sse_service.dispatch_event(SseEventFrontendNotification(color="negative", message=f"{exc}", caption="Share/Print Error"))
            raise RuntimeError(f"Process failed, error {exc}") from exc

        self._information_service.stats_counter_increment("shares")
        if max_shares > 0:
            self._information_service.stats_counter_increment_limite(action_config.name)
            current_shares = limites[action_config.name]
            self._sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="info",
                    message=f"{action_config.trigger.ui_trigger.title} quota : {current_shares}/{max_shares}",
                    caption="Share/Print quota",
                )
            )

    def is_blocked(self):
        return self.remaining_time_blocked() > 0.0

    def remaining_time_blocked(self) -> float:
        if self._last_print_time is None:
            return 0.0

        delta = time.time() - self._last_print_time
        if delta >= self._last_printing_blocked_time:
            # last print is longer than configured time in the past - return 0 to indicate no wait time
            return 0.0
        else:
            # there is some time to wait left.
            return self._last_printing_blocked_time - delta

    def _start_time_blocked(self, printing_blocked_time: int):
        self._last_print_time = time.time()
        self._last_printing_blocked_time = printing_blocked_time

        # TODO: add some timer/coroutine to send regular update to UI with current remaining time blocked

    def _print_timer_fun(self):
        ## thread to send updates to client about remaining blocked time
        pass
