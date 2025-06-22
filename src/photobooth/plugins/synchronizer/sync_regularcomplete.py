import logging
import time
from pathlib import Path

from ...utils.resilientservice import ResilientService
from .connectors.abstractconnector import AbstractConnector
from .threadedqueueprocessor import ThreadedQueueProcessor
from .types import Priority, PriorizedTask, SyncTaskUpload
from .utils import get_remote_filepath

logger = logging.getLogger(__name__)


class SyncRegularcomplete(ResilientService):
    def __init__(self, connector: AbstractConnector, threadedqueueprocessor: ThreadedQueueProcessor, local_root_dir: Path):
        super().__init__()

        self._control_connection: AbstractConnector = connector
        self._threadedqueueprocessor: ThreadedQueueProcessor = threadedqueueprocessor
        self._local_root_dir: Path = local_root_dir

        self.start()

    def __str__(self):
        return f"{self.__class__.__name__}: {self._control_connection}"

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def setup_resource(self):
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

            for local_path in Path(self._local_root_dir).glob("**/*.*"):
                if self._stop_event.is_set():
                    return

                remote_path = get_remote_filepath(local_path)
                is_same_file = self._control_connection.get_remote_samefile(local_path, remote_path)

                if not is_same_file:
                    self._threadedqueueprocessor.put_to_queue(PriorizedTask(Priority.LOW, SyncTaskUpload(local_path, remote_path)))
                    logger.debug(f"added {local_path} to upload queue in {self._control_connection}")

            tme = time.time()
            duration = round(tme - tms)
            logger.info(f"Completed regular re-sync check after {duration}s duration. Media was added to the queue to upload separately if needed.")

            ## Sleeping phase
            while not self._stop_event.is_set():
                if slept_counter < sync_every_x_seconds:
                    time.sleep(sleep_time)
                    slept_counter += sleep_time
                    continue
                else:
                    slept_counter = 0
                    break  # next sync run.
