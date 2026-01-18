import logging
import time
from datetime import datetime, timedelta
from importlib import resources
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from rclone_api.api import RcloneApi

from ... import MEDIA_PATH
from ...models.genericstats import GenericStats, SubList, SubStats
from ...utils.resilientservice import ResilientService
from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import SynchronizerConfig
from .types import Stats, TaskCopy, TaskDelete, TaskSyncType
from .utils import get_corresponding_remote_file

logger = logging.getLogger(__name__)


class SynchronizerRclone(ResilientService, BasePlugin[SynchronizerConfig]):
    def __init__(self):
        super().__init__()
        self._config = SynchronizerConfig()

        self._rclone_client: RcloneApi | None = None
        self._stats = Stats()

    def __str__(self):
        return "SynchronizerRclone"

    @hookimpl
    def start(self):
        if not self._config.common.enabled:
            logger.info("Synchronizer Plugin is disabled")
            return

        self._rclone_client = RcloneApi(
            log_file=Path("log/rclone.log") if self._config.rclone_client_config.rclone_enable_logging else None,
            log_level=self._config.rclone_client_config.rclone_log_level,
            transfers=self._config.rclone_client_config.rclone_transfers,
            checkers=self._config.rclone_client_config.rclone_checkers,
            enable_webui=self._config.rclone_client_config.enable_webui,
            # bwlimit="1M",
        )

        super().start()

    @hookimpl
    def stop(self):
        super().stop()

    def setup_resource(self):
        assert self._rclone_client

        self._rclone_client.start()

    def teardown_resource(self):
        if self._rclone_client:
            self._rclone_client.stop()

    def wait_until_ready(self, timeout: float = 5) -> None:
        if self._rclone_client:
            self._rclone_client.wait_until_operational(timeout)

    def run_service(self):
        sync_every_x_seconds = 60 * self._config.common.full_sync_interval
        slept_counter = 0
        sleep_time = 0.5
        assert self._rclone_client

        self._copy_sharepage_to_remotes()

        ####

        while not self._stop_event.is_set():
            ## Monitoring phase

            self._stats.last_check_started = datetime.now()
            full_sync_jobids: list[int] = []

            for remote in self._config.remotes:
                if not (remote.enabled and remote.enable_regular_sync):
                    continue

                job = self._rclone_client.sync_async(
                    str(Path(MEDIA_PATH).absolute()),
                    f"{remote.name}{Path(remote.subdir, get_corresponding_remote_file(Path(MEDIA_PATH))).as_posix()}",
                )

                full_sync_jobids.append(job.jobid)

            ## wait until finished - TODO: maybe stop if an immediate sync is requested.
            if full_sync_jobids:
                logger.info("Regular full sync triggered")
                self._rclone_client.wait_for_jobs(full_sync_jobids)
                logger.info("All enabled full sync jobs finished, going to sleep now.")

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
        if not self.is_running():
            return

        assert self._rclone_client

        for remote in self._config.remotes:
            if not (remote.enabled and remote.enable_immediate_sync):
                continue

            try:
                if isinstance(task, TaskCopy):
                    self._rclone_client.copyfile_async(
                        str(Path.cwd().absolute()),
                        f"{task.file_local}",
                        remote.name,
                        Path(remote.subdir, task.file_remote).as_posix(),
                    )

                elif isinstance(task, TaskDelete):
                    self._rclone_client.deletefile(
                        remote.name,
                        Path(remote.subdir, task.file_remote).as_posix(),
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

        assert self._rclone_client

        try:
            core_stats = self._rclone_client.core_stats()
            job_list = self._rclone_client.job_list()
        except Exception as exc:
            return GenericStats(id="hook-plugin-synchronizer", name="Synchronizer", stats=[SubStats("Error", f"Cannot gather stats, reason: {exc}")])

        out = GenericStats(id="hook-plugin-synchronizer", name="Synchronizer")

        out.stats.append(
            SubList(
                name="Rclone Core Stats",
                val=[
                    SubStats(
                        "Amount Finished", (float(core_stats.bytes) / float(core_stats.totalBytes) * 100.0) if core_stats.totalBytes else 0, unit="%"
                    ),
                    SubStats("Amount", core_stats.bytes / 1024 / 1024, unit="Mb"),
                    SubStats("Total Amount", core_stats.totalBytes / 1024 / 1024, unit="Mb"),
                    SubStats("eta", core_stats.eta, unit="s"),
                    SubStats("errors", core_stats.errors),
                    SubStats("speed", core_stats.speed / 1014 / 1014, decimals=1, unit="Mb/s"),
                    SubStats("totalTransfers", core_stats.totalTransfers),
                    SubStats("deletes", core_stats.deletes),
                ],
            )
        )
        out.stats.append(SubStats("lastError", core_stats.lastError))

        out.stats.append(
            SubList(
                name="Regular Full Sync Stats",
                val=[
                    SubStats(
                        "last_check_started", self._stats.last_check_started.astimezone().strftime("%X") if self._stats.last_check_started else None
                    ),
                    SubStats("next_check", self._stats.next_check.astimezone().strftime("%X") if self._stats.next_check else None),
                ],
            )
        )

        for idx, active_transfer in enumerate(core_stats.transferring):
            out.stats.append(
                SubList(
                    name=f"Transfer #{idx}",
                    val=[
                        SubStats("file", active_transfer.name),
                        SubStats("percentage", active_transfer.percentage, unit="%"),
                        SubStats("speedAvg", active_transfer.speedAvg / 1014 / 1014, decimals=1, unit="MB/s"),
                    ],
                )
            )

        for running_jobid in sorted(job_list.runningIds):
            job_status = self._rclone_client.job_status(running_jobid)

            if not job_status.finished:
                out.stats.append(
                    SubList(
                        name=f"Running Job #{running_jobid}",
                        val=[
                            SubStats("startTime", job_status.startTime),
                            SubStats("finished", job_status.finished),
                            SubStats("success", job_status.success),
                            SubStats("progress", job_status.progress),
                        ],
                    )
                )

        return out

    def _copy_sharepage_to_remotes(self):
        assert self._rclone_client

        dlportal_source_path = Path(str(resources.files("web").joinpath("sharepage/index.html")))
        assert dlportal_source_path.is_file()

        for remote in self._config.remotes:
            if not remote.enable_sharepage_sync:
                continue

            # add to queue for later upload.
            # this way if no internet the startup is not causing issues preventing the complete app from startup
            logger.info(f"update shareportal to {remote.name}/{remote.subdir}")
            self._rclone_client.copyfile_async(
                dlportal_source_path.parent.absolute().as_posix(),
                dlportal_source_path.name,
                remote.name,
                Path(remote.subdir, dlportal_source_path.name).as_posix(),
            )

    @hookimpl
    def get_share_links(self, filepath_local: Path, identifier: UUID) -> list[str]:
        if not self.is_running():
            return []

        assert self._rclone_client

        share_links: list[str] = []

        if not self._config.common.enabled_share_links:
            logger.info("share link generation is disabled globally in synchronizer plugin")
            return []

        if self._config.common.enabled_custom_qr_url:
            formatted_custom_qr_url = self._config.common.custom_qr_url.format(
                filename=filepath_local.name,
                identifier=str(identifier),
            )

            share_links.append(formatted_custom_qr_url)

        for remote in self._config.remotes:
            shareconfig = remote.shareconfig
            mediaitem_link: str | None = None

            if not shareconfig.enabled:
                continue

            if shareconfig.manual_public_link:
                mediaitem_link = shareconfig.manual_public_link.format(
                    filename=filepath_local.name,
                    identifier=str(identifier),
                )
            else:
                try:
                    mediaitem_link = self._rclone_client.publiclink(
                        remote.name,
                        Path(remote.subdir, get_corresponding_remote_file(filepath_local)).as_posix(),
                    ).link
                except Exception as exc:
                    logger.error(f"could not create public link due to error: {exc}")

            if not mediaitem_link:
                logger.error(
                    f"could not generate a link for {filepath_local.name} using remote {remote.name}. "
                    "If the remote does not support public links, you need to provide a manual url override or use a different provider."
                )
                continue

            # sanity check on sharepage url
            if shareconfig.use_sharepage and not shareconfig.sharepage_url:
                logger.error(
                    f"can't generate a link because the sharepage shall be used but no URL was given in the configuration for {remote.description}"
                )
                continue

            if shareconfig.use_sharepage:
                shareportal_url = f"{str(shareconfig.sharepage_url).rstrip('/')}#/?url="
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
