import logging
import time
from pathlib import Path

from ...utils.resilientservice import ResilientService
from .connectors.abstractconnector import AbstractConnector
from .utils import get_remote_filepath

logger = logging.getLogger(__name__)


class SyncRegularcomplete(ResilientService):
    def __init__(self, connector: AbstractConnector, local_root_dir: Path):
        super().__init__()

        self._connector: AbstractConnector = connector
        self._local_root_dir: Path = local_root_dir

        self.start()

    def __str__(self):
        return f"{self.__class__.__name__}: {self._connector}"

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def setup_resource(self):
        self._connector.connect()

    def teardown_resource(self):
        self._connector.disconnect()

    def run_service(self):
        sync_every_x_seconds = 60 * 5
        slept_counter = 0
        sleep_time = 0.5

        while not self._stop_event.is_set():
            logger.info("Monitoring media files for regular re-sync.")

            for local_path in Path(self._local_root_dir).glob("**/*.*"):
                if self._stop_event.is_set():
                    return

                try:
                    remote_path = get_remote_filepath(local_path)
                    is_same_file = self._connector.get_remote_samefile(local_path, remote_path)

                    if not is_same_file:
                        self._connector.do_upload(local_path, remote_path)
                        logger.info(f"uploaded: {local_path} to {remote_path} on using connector {self._connector}")

                except Exception as e:
                    logger.error(f"error processing file {local_path}: {e}")
                    raise e

            while not self._stop_event.is_set():
                if slept_counter < sync_every_x_seconds:
                    time.sleep(sleep_time)
                    slept_counter += sleep_time
                    continue
                else:
                    slept_counter = 0
                    break  # next sync run.
