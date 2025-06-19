import logging
import time
from pathlib import Path

from photobooth.utils.resilientservice import ResilientService

from .connectors.base import AbstractConnector

logger = logging.getLogger(__name__)


class SyncRegularcomplete(ResilientService):
    def __init__(self, connector: AbstractConnector, local_root_dir: Path):
        super().__init__()

        self._connector: AbstractConnector = connector
        self._local_root_dir: Path = local_root_dir

        # start with fresh queue
        # self._queue: queueSyncType = queueSyncType()
        # start resilient service activates below functions
        self.start()

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def setup_resource(self):
        sync_every_x_seconds = 60
        slept_counter = 0
        sleep_time = 0.5

        while not self._stop_event.is_set():
            print("Starte Initial-datei sync...")

            for local_path in Path(self._local_root_dir).glob("**/*.*"):
                if self._stop_event.is_set():
                    print("stop queueuing because shutdown requested.")
                    return

                try:
                    remote_path = Path("TODO.file")
                    # TODO: # remote_path = get_remote_filepath(local_path)
                    is_same_file = self._connector.get_remote_samefile(local_path, remote_path)

                    if not is_same_file:
                        self._connector.do_upload(local_path, remote_path)
                        print(f"queueud for upload: {local_path}")

                except Exception as e:
                    print(f"Fehler bei verarbeitung von {local_path}: {e}")
                    raise e

            while True:
                if slept_counter < sync_every_x_seconds:
                    time.sleep(sleep_time)
                    slept_counter += sleep_time
                    continue
                else:
                    slept_counter = 0
                    break  # next sync run.

            print("Initial-Synchronisation abgeschlossen.")
