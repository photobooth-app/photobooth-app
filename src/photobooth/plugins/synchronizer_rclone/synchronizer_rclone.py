import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib import resources
from pathlib import Path
from urllib.parse import quote

from ...models.genericstats import DisplayEnum, GenericStats, SubList, SubStats
from ...utils.rclone_client.client import RcloneClient
from ...utils.resilientservice import ResilientService
from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import SynchronizerConfig
from .types import TaskCopy, TaskDelete, TaskSyncType
from .utils import get_corresponding_remote_file

logger = logging.getLogger(__name__)


@dataclass
class Stats:
    check_active: bool = False
    last_check_started: datetime | None = None  # datetime to convert .astimezone().strftime('%Y%m%d-%H%M%S')
    last_duration: float | None = None
    next_check: datetime | None = None
    files_queued_last_check: int = 0


class SynchronizerRclone(ResilientService, BasePlugin[SynchronizerConfig]):
    def __init__(self):
        super().__init__()
        self._config = SynchronizerConfig()

        self.__rclone_client: RcloneClient = RcloneClient(
            log_level=self._config.common.rclone_log_level,
            transfers=self._config.common.rclone_transfers,
            checkers=self._config.common.rclone_checkers,
        )
        self.__local_base_path = Path("./media/")
        self._service_ready: threading.Event = threading.Event()
        self._stats = Stats()

    def __str__(self):
        return "SynchronizerRclone ()"

    def reset(self): ...

    @hookimpl
    def start(self):
        self.reset()

        if not self._config.common.enabled:
            logger.info("Synchronizer Plugin is disabled")
            return

        super().start()

    @hookimpl
    def stop(self):
        super().stop()

    def setup_resource(self):
        self.__rclone_client.start()

    def teardown_resource(self):
        self._service_ready.clear()

        if self.__rclone_client:
            self.__rclone_client.stop()

    def wait_until_ready(self, timeout: float = 5) -> bool:
        return self._service_ready.wait(timeout=timeout)

    def run_service(self):
        sync_every_x_seconds = 60 * 5
        slept_counter = 0
        sleep_time = 0.5
        assert self.__rclone_client

        for _ in range(30):
            if self.__rclone_client.operational():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("rclone did not become alive after 20 attempts")

        self._service_ready.set()

        self.copy_shareportal_to_remotes()

        ####

        while not self._stop_event.is_set():
            ## Monitoring phase
            logger.info("Regular full sync starts")

            self._stats.last_check_started = datetime.now()

            for remote in self._config.remotes:
                if not (remote.enabled and remote.syncconfig.enable_regular_sync):
                    continue

                self.__rclone_client.sync_async(
                    str(Path("media").absolute()),
                    f"{remote.name.rstrip(':')}:{remote.subdir.rstrip('/')}/",
                )

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

    def _put_to_rclone_job_manager(self, task: TaskSyncType):
        for remote in self._config.remotes:
            if not (remote.enabled and remote.syncconfig.enable_immediate_sync):
                continue

            try:
                if isinstance(task, TaskCopy):
                    self.__rclone_client.copyfile_async(
                        str(Path.cwd().absolute()),
                        f"{task.file_local}",
                        f"{remote.name.rstrip(':')}:",
                        f"{remote.subdir.rstrip('/')}/{task.file_remote}",
                    )

                elif isinstance(task, TaskDelete):
                    self.__rclone_client.deletefile(
                        f"{remote.name.rstrip(':')}:",
                        f"{remote.subdir.rstrip('/')}/{task.file_remote}",
                    )
                # else never as per typing
            except Exception as exc:
                logger.exception(exc)
                logger.error(f"failed processing task {task}, error {exc}")
                # TODO: what if task failed? reinsert to sync queue?

    @hookimpl
    def get_stats(self) -> GenericStats | None:
        if self._config.common.enabled is False:
            # avoids display of an empty stats object in the admin dashboard
            return None

        try:
            core_stats = self.__rclone_client.core_stats()
        except Exception as exc:
            logger.error(f"cannot gather stats, error: {exc}")
            return GenericStats(id="hook-plugin-synchronizer", name="Synchronizer", stats=[SubStats("Error", "Cannot connect to Rclone API!")])

        out = GenericStats(id="hook-plugin-synchronizer", name="Synchronizer")
        out.stats.append(
            SubList(
                "Rclone Core Stats",
                val=[
                    SubStats("bytes", core_stats.bytes),
                    SubStats("checks", core_stats.checks),
                    SubStats("transfers", core_stats.transfers),
                    SubStats("deletes", core_stats.deletes),
                    SubStats("totalTransfers", core_stats.totalTransfers),
                    SubStats("errors", core_stats.errors),
                    SubStats("eta", core_stats.eta),
                ],
            )
        )
        out.stats.append(SubStats("lastError", core_stats.lastError))

        for active_transfer in core_stats.transferring:
            out.stats.append(
                SubList(
                    name=str(active_transfer.name),
                    val=[
                        SubStats("percentage", active_transfer.percentage, unit="%"),
                        SubStats("speedAvg", active_transfer.speedAvg, unit=""),
                    ],
                )
            )

        out.stats.append(
            SubList(
                name="Regular Full Sync Stats",
                val=[
                    SubStats("check_active", self._stats.check_active, display=DisplayEnum.spinner),
                    SubStats(
                        "last_check_started", self._stats.last_check_started.astimezone().strftime("%X") if self._stats.last_check_started else None
                    ),
                    SubStats("last_duration", self._stats.last_duration, unit="s"),
                    SubStats("next_check", self._stats.next_check.astimezone().strftime("%X") if self._stats.next_check else None),
                    SubStats("files_queued_last_check", self._stats.files_queued_last_check),
                ],
            )
        )

        return out

    def copy_shareportal_to_remotes(self):
        dlportal_source_path = Path(str(resources.files("web").joinpath("download/index.html")))
        assert dlportal_source_path.is_file()

        for remote in self._config.remotes:
            if not remote.shareconfig.downloadportal_autoupload:
                continue

            # add to queue for later upload.
            # this way if no internet the startup is not causing issues preventing the complete app from startup
            logger.info(f"update shareportal to {remote.name}/{remote.subdir}")
            self.__rclone_client.copyfile_async(
                dlportal_source_path.parent.absolute().as_posix(),
                dlportal_source_path.name,
                f"{remote.name.rstrip(':')}:",
                f"{remote.subdir.rstrip('/')}/{dlportal_source_path.name}",
            )

    @hookimpl
    def get_share_links(self, filepath_local: Path) -> list[str]:
        share_links: list[str] = []

        if not self._config.common.enable_share_links:
            logger.info("share link generation is disabled globally in synchronizer plugin")
            return []

        for remote in self._config.remotes:
            mediaitem_link: str | None = None

            if not remote.shareconfig.enable_share_link:
                continue

            if remote.shareconfig.publiclink_override:
                mediaitem_link = (
                    str(remote.shareconfig.publiclink_override).rstrip("/") + "/" + get_corresponding_remote_file(filepath_local).as_posix()
                )
            else:
                try:
                    mediaitem_link = self.__rclone_client.publiclink(
                        f"{remote.name.rstrip(':')}:",
                        get_corresponding_remote_file(filepath_local).as_posix(),
                    )
                except Exception as exc:
                    logger.warning(f"could not create public link due to error: {exc}")

            if not mediaitem_link:
                logger.error(
                    f"could not generate a link for {filepath_local} using remote {remote.name}. "
                    "If the remote does not support public links, you need to provide an override or use a different provider."
                )
                continue

            # sanity check on downloadportal url
            if remote.shareconfig.use_downloadportal and not remote.shareconfig.shareportal_url:
                logger.error(f"cannot share because use of downloadportal is enabled but no URL available for {remote.description}")
                continue

            if remote.shareconfig.use_downloadportal:
                shareportal_url = f"{str(remote.shareconfig.shareportal_url).rstrip('/')}/#/?url="
                mediaitem_url_safe = quote(mediaitem_link, safe="")
                out = shareportal_url + mediaitem_url_safe
            else:
                out = mediaitem_link

            share_links.append(out)

        return share_links

    @hookimpl
    def collection_original_file_added(self, files: list[Path]):
        for file in files:
            self._put_to_rclone_job_manager(TaskCopy(file, get_corresponding_remote_file(file)))

    @hookimpl
    def collection_files_added(self, files: list[Path]):
        for file in files:
            self._put_to_rclone_job_manager(TaskCopy(file, get_corresponding_remote_file(file)))

    @hookimpl
    def collection_files_updated(self, files: list[Path]):
        for file in files:
            self._put_to_rclone_job_manager(TaskCopy(file, get_corresponding_remote_file(file)))

    @hookimpl
    def collection_files_deleted(self, files: list[Path]):
        for file in files:
            self._put_to_rclone_job_manager(TaskDelete(get_corresponding_remote_file(file)))
