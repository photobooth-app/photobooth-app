import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from ...utils.resilientservice import ResilientService
from .connectors.abstractconnector import AbstractConnector
from .queueprocessor import QueueProcessor
from .types import Priority, PriorizedTask, SyncTaskUpload
from .utils import get_remote_filepath

logger = logging.getLogger(__name__)


@dataclass
class Stats:
    check_active: bool = False
    last_check_started: datetime | None = None  # datetime to convert .astimezone().strftime('%Y%m%d-%H%M%S')
    last_duration: float | None = None
    next_check: datetime | None = None
    files_queued_last_check: int = 0


class SyncRegularcomplete(ResilientService):
    def __init__(self, connector: AbstractConnector, threadedqueueprocessor: QueueProcessor, local_root_dir: Path):
        super().__init__()

        self._control_connection: AbstractConnector = connector
        self._threadedqueueprocessor: QueueProcessor = threadedqueueprocessor
        self._local_root_dir: Path = local_root_dir

        self._stats: Stats = Stats()

        self.start()

    def __str__(self):
        return f"Regular Sync ({self._control_connection})"

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def setup_resource(self):
        self._stats = Stats()
        self._control_connection.connect()

    def teardown_resource(self):
        self._control_connection.disconnect()

    def run_service(self):
        sync_every_x_seconds = 60 * 5
        slept_counter = 0
        sleep_time = 0.5

        while not self._stop_event.is_set():
            ## Monitoring phase
            logger.info(f"Start regular re-sync check for {self._control_connection}.")
            tms = time.time()
            self._stats.last_check_started = datetime.now()
            self._stats.check_active = True
            self._stats.files_queued_last_check = 0

            for local_path in Path(self._local_root_dir).glob("**/*.*"):
                if self._stop_event.is_set():
                    return

                remote_path = get_remote_filepath(local_path)
                is_same_file = self._control_connection.do_check_issame(local_path, remote_path)

                if not is_same_file:
                    self._threadedqueueprocessor.put_to_queue(PriorizedTask(Priority.LOW, SyncTaskUpload(local_path, remote_path)))
                    self._stats.files_queued_last_check += 1
                    # logger.debug(f"added {local_path} to upload queue in {self._control_connection}")

            tme = time.time()
            duration = round(tme - tms, 1)
            self._stats.check_active = False
            self._stats.last_duration = duration
            logger.info(f"Completed regular re-sync check after {duration}s duration. Media was added to the queue to upload separately if needed.")

            ## Sleeping phase
            self._stats.next_check = datetime.now() + timedelta(seconds=sync_every_x_seconds)
            while not self._stop_event.is_set():
                if slept_counter < sync_every_x_seconds:
                    time.sleep(sleep_time)
                    slept_counter += sleep_time
                    continue
                else:
                    slept_counter = 0
                    break  # next sync run.
