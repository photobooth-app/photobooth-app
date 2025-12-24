import logging
import time
from pathlib import Path

from ...utils import rclone
from ...utils.resilientservice import ResilientService
from .config import RcloneRemoteConfig, SyncFullConfig

logger = logging.getLogger(__name__)


class SyncFull(ResilientService):
    def __init__(self, local_root_dir: Path, config: SyncFullConfig, rclone_config: RcloneRemoteConfig):
        super().__init__()

        self.__config: SyncFullConfig = config
        self.__rclone_config: RcloneRemoteConfig = rclone_config
        self.__local_root_dir: Path = local_root_dir

    # def __str__(self):
    #     return f"Regular Sync ({self._control_connection})"

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def setup_resource(self): ...

    def teardown_resource(self): ...

    def run_service(self):
        sync_every_x_seconds = 60 * 5
        slept_counter = 0
        sleep_time = 0.5

        while not self._stop_event.is_set():
            ## Monitoring phase
            logger.info(f"Start regular re-sync check for {self.__rclone_config.remote}.")

            self.check_active = True

            process = rclone.sync(
                str(self.__local_root_dir),
                f"{self.__rclone_config.remote.rstrip(':')}:{self.__rclone_config.remote_base_dir.rstrip('/')}/",
            )
            process.wait()

            logger.info("Completed regular re-sync.")

            ## Sleeping phase
            self.check_active = False
            while not self._stop_event.is_set():
                if slept_counter < sync_every_x_seconds:
                    time.sleep(sleep_time)
                    slept_counter += sleep_time
                    continue
                else:
                    slept_counter = 0
                    break  # next sync run.
