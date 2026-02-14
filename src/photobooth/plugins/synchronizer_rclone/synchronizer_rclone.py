import logging
from importlib import resources
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from rclone_api.api import RcloneApi

from ...models.genericstats import GenericStats, SubList, SubStats
from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import RemoteConfig, SynchronizerConfig
from .immediate_synchronizer import ThreadedImmediateSyncPipeline
from .regular_synchronizer import ThreadedRegularSync
from .types import TaskCopy, TaskDelete
from .utils import get_corresponding_remote_file

logger = logging.getLogger(__name__)


class SynchronizerRclone(BasePlugin[SynchronizerConfig]):
    def __init__(self):
        super().__init__()
        self._config = SynchronizerConfig()

        self._rclone_client: RcloneApi | None = None

        self._immediate_pipeline: ThreadedImmediateSyncPipeline | None = None
        self._regular_sync: ThreadedRegularSync | None = None

    def __str__(self):
        return "SynchronizerRclone"

    @hookimpl
    def start(self):
        if not self._config.common.enabled:
            logger.info("Synchronizer Plugin is disabled")
            return

        _log_file = Path("log/rclone.log") if self._config.rclone_client_config.rclone_enable_logging else None
        _config_file = Path(self._config.rclone_client_config.local_config_file) if self._config.rclone_client_config.use_local_config_file else None
        _immediate_sync_remotes: list[RemoteConfig] = [x for x in self._config.remotes if x and x.enable_immediate_sync]
        _full_sync_remotes: list[RemoteConfig] = [x for x in self._config.remotes if x and x.enable_regular_sync]
        _copy_sharepage_to_remotes = [x for x in self._config.remotes if x.enabled and x.enable_sharepage_sync]

        self._rclone_client = RcloneApi(
            log_file=_log_file,
            log_level=self._config.rclone_client_config.rclone_log_level,
            transfers=self._config.rclone_client_config.rclone_transfers,
            checkers=self._config.rclone_client_config.rclone_checkers,
            enable_webui=self._config.rclone_client_config.enable_webui,
            config_file=_config_file,
            # bwlimit="1M",
        )
        self._rclone_client.start()

        self._regular_sync = ThreadedRegularSync(self._rclone_client, _full_sync_remotes, sync_interval_s=60 * self._config.common.full_sync_interval)
        self._immediate_pipeline = ThreadedImmediateSyncPipeline(self._rclone_client, _immediate_sync_remotes)

        for r in _copy_sharepage_to_remotes:
            self._copy_sharepage_to_remotes(r)

    @hookimpl
    def stop(self):

        if self._regular_sync:
            self._regular_sync.stop()

        if self._immediate_pipeline:
            self._immediate_pipeline.stop()

        if self._rclone_client:
            self._rclone_client.stop()

    def wait_until_ready(self, timeout: float = 5) -> None:
        if not self._rclone_client:
            raise RuntimeError("cannot wait for the service to be ready if not enabled and started before!")

        if self._rclone_client:
            self._rclone_client.wait_until_operational(timeout)

    @hookimpl
    def get_stats(self) -> GenericStats | None:
        if self._config.common.enabled is False:
            # avoids display of an empty stats object in the admin dashboard
            return None
        if not (self._rclone_client and self._immediate_pipeline and self._regular_sync):
            return None

        try:
            core_stats = self._rclone_client.core_stats()
            job_list = self._rclone_client.job_list()
            immediate_stats = self._immediate_pipeline.get_stats()
            regular_stats = self._regular_sync.get_stats()
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
                name="Immediate Sync Stats (#files since app start)",
                val=[
                    SubStats("Pending", immediate_stats.pending),
                    SubStats("Transferring", immediate_stats.transferring),
                    SubStats("Finished", immediate_stats.finished),
                    SubStats("Failed", immediate_stats.failed),
                    SubStats("Total", immediate_stats.total),
                ],
            )
        )
        out.stats.append(
            SubList(
                name="Regular Full Sync Stats",
                val=[
                    SubStats(
                        "last_check_started",
                        regular_stats.last_check_started.astimezone().strftime("%X") if regular_stats.last_check_started else None,
                    ),
                    SubStats("next_check", regular_stats.next_check.astimezone().strftime("%X") if regular_stats.next_check else None),
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

    def _copy_sharepage_to_remotes(self, remote: RemoteConfig):
        assert self._rclone_client

        dlportal_source_path = Path(str(resources.files("web").joinpath("sharepage/index.html")))
        assert dlportal_source_path.is_file()

        # add to queue for later upload.
        # this way if no internet the startup is not causing issues preventing the complete app from startup
        logger.info(f"update shareportal to {remote.name}{remote.subdir}")
        self._rclone_client.copyfile_async(
            dlportal_source_path.parent.absolute().as_posix(),
            dlportal_source_path.name,
            remote.name,
            Path(remote.subdir, dlportal_source_path.name).as_posix(),
        )

    @hookimpl
    def get_share_links(self, filepath_local: Path, identifier: UUID) -> list[str]:
        if not self._rclone_client:
            return []

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
    def collection_files_added(self, files: list[Path], priority_modifier: int):
        if not self._immediate_pipeline:
            return

        priority = 10 + priority_modifier
        for file in files:
            self._immediate_pipeline.submit(TaskCopy(file), priority=priority)

    @hookimpl
    def collection_files_updated(self, files: list[Path]):
        if not self._immediate_pipeline:
            return

        for file in files:
            self._immediate_pipeline.submit(TaskCopy(file), priority=15)

    @hookimpl
    def collection_files_deleted(self, files: list[Path]):
        if not self._immediate_pipeline:
            return

        for file in files:
            self._immediate_pipeline.submit(TaskDelete(file), priority=19)
