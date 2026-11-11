import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

import psutil
from rclone_api.api import RcloneApi
from rclone_api.exceptions import RcloneProcessException

from ... import MEDIA_PATH
from ...utils.stoppablethread import StoppableThread
from .config import RemoteConfig
from .utils import ensure_remote_base_path, get_corresponding_remote_file

logger = logging.getLogger(__name__)


@dataclass
class Stats:
    last_check_started: datetime | None = None  # datetime to convert .astimezone().strftime('%Y%m%d-%H%M%S')
    next_check: datetime | None = None


class DiskPart(Protocol):
    @property
    def device(self) -> str: ...
    @property
    def mountpoint(self) -> str: ...
    @property
    def fstype(self) -> str: ...
    @property
    def opts(self) -> str: ...


class ThreadedRegularSync:
    def __init__(self, rclone: RcloneApi, fullsync_remotes: list[RemoteConfig], sync_interval_s: int = 300, usb_drive_change_monitor: bool = True):
        self.rclone: RcloneApi = rclone
        self.remotes: list[RemoteConfig] = fullsync_remotes  # all remotes in a list to sync to
        self.sync_interval_s: int = sync_interval_s
        self.usb_drive_change_monitor: bool = usb_drive_change_monitor

        self._stats = Stats()

        self._worker = StoppableThread(target=self._worker_loop, name="rclone-regular-worker", daemon=True)
        self._worker.start()

    def stop(self):
        if self._worker:
            self._worker.stop()
            self._worker.join()

    def get_stats(self) -> Stats:
        return self._stats

    def get_current_removable_media(self):
        """Returns set of removable drives detected on the computer."""
        if self.usb_drive_change_monitor:
            return {device for device in psutil.disk_partitions(all=False)}
        else:
            return set()

    def _worker_loop(self):
        last_run = 0  # 0 to ensure first loop runs always.
        _previous_devices = self.get_current_removable_media()

        while not self._worker.stopped():
            # working phase
            full_sync_jobids: list[int] = []

            self._stats.last_check_started = datetime.now()

            for r in self.remotes:
                try:
                    # creates bucket/subdir if a bucket is configured, otherwise no-op
                    ensure_remote_base_path(self.rclone, r)
                    # returns a list of the remote main dir or raises an exception 404 if the folder does not exist
                    # this is used to avoid submitting operations to a usb drive that is not attached currently.
                    self.rclone.ls(r.name, r.base_path)
                except RcloneProcessException as exc:
                    logger.error(f"{r.name}{r.base_path} not available, error code {exc.status}, skipping.")
                    continue
                except Exception as exc:
                    logger.error(f"{r.name}{r.base_path} could not be prepared: {exc}, skipping.")
                    continue

                if r.copy_only_mode:
                    logger.info(f"copy files to '{r.name}{r.base_path}'")
                    fn_op = self.rclone.copy_async
                else:
                    logger.info(f"sync files to '{r.name}{r.base_path}'")
                    fn_op = self.rclone.sync_async

                job = fn_op(
                    str(Path(MEDIA_PATH).absolute()),
                    f"{r.name}{Path(r.base_path, get_corresponding_remote_file(Path(MEDIA_PATH))).as_posix()}",
                )

                full_sync_jobids.append(job.jobid)

            ## wait until finished
            if full_sync_jobids:
                self.rclone.wait_for_jobs(full_sync_jobids)
                logger.info("All enabled rclone jobs finished, waiting for next run...")

            ## Sleeping phase
            self._stats.next_check = datetime.now() + timedelta(seconds=self.sync_interval_s)
            last_run = time.monotonic()  # update at the very end because process could be time consuming.

            while not self._worker.stopped():
                current_devices = self.get_current_removable_media()
                devices_added = current_devices - _previous_devices
                devices_removed = _previous_devices - current_devices

                if (time.monotonic() - last_run) > self.sync_interval_s:
                    logger.info("Starting regular full rclone synchronization")

                    break  # to go to working phase.
                elif devices_added:
                    # detected a previously unavailable drive - next run due
                    logger.info(f"USB device {[f'{device.device} ({device.mountpoint})' for device in devices_added]} has been detected.")
                    logger.info("Starting regular full rclone sync.")
                    _previous_devices = current_devices

                    break  # to go to working phase.
                elif devices_removed:
                    logger.info(f"USB device {[f'{device.device} ({device.mountpoint})' for device in devices_removed]} has been removed.")
                    _previous_devices = current_devices

                # otherwise sleep until run due...
                time.sleep(1)
