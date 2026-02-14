import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from rclone_api.api import RcloneApi

from ... import MEDIA_PATH
from ...utils.stoppablethread import StoppableThread
from .config import RemoteConfig
from .utils import get_corresponding_remote_file

logger = logging.getLogger(__name__)


@dataclass
class Stats:
    last_check_started: datetime | None = None  # datetime to convert .astimezone().strftime('%Y%m%d-%H%M%S')
    next_check: datetime | None = None


class ThreadedRegularSync:
    def __init__(self, rclone: RcloneApi, fullsync_remotes: list[RemoteConfig], sync_interval_s: int = 300):
        self.rclone: RcloneApi = rclone
        self.remotes: list[RemoteConfig] = fullsync_remotes  # all remotes in a list to sync to
        self.sync_interval_s: int = sync_interval_s

        self._stats = Stats()

        self._worker = StoppableThread(target=self._worker_loop, name="rclone-regular-worker", daemon=True)
        self._worker.start()

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------
    def stop(self):
        if self._worker:
            self._worker.stop()
            self._worker.join()

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> Stats:
        return self._stats

    # --------------------------------------------------------
    # Worker Loop
    # --------------------------------------------------------

    def _worker_loop(self):
        slept_counter = 0
        sleep_time = 0.5

        while not self._worker.stopped():
            ## Monitoring phase

            self._stats.last_check_started = datetime.now()
            full_sync_jobids: list[int] = []

            for remote in self.remotes:
                job = self.rclone.sync_async(
                    str(Path(MEDIA_PATH).absolute()),
                    f"{remote.name}{Path(remote.subdir, get_corresponding_remote_file(Path(MEDIA_PATH))).as_posix()}",
                )

                full_sync_jobids.append(job.jobid)

            ## wait until finished - TODO: maybe stop if an immediate sync is requested.
            if full_sync_jobids:
                logger.info("Regular full sync triggered")
                self.rclone.wait_for_jobs(full_sync_jobids)
                logger.info("All enabled full sync jobs finished, going to sleep now.")

            ## Sleeping phase
            self._stats.next_check = datetime.now() + timedelta(seconds=self.sync_interval_s)
            while not self._worker.stopped():
                if slept_counter < self.sync_interval_s:
                    time.sleep(sleep_time)
                    slept_counter += sleep_time
                    continue
                else:
                    slept_counter = 0
                    break  # next sync run.
