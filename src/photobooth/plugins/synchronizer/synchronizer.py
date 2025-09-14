import logging
from pathlib import Path

from ...models.genericstats import DisplayEnum, GenericStats, SubList, SubStats
from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import SynchronizerConfig
from .connectors import connector_factory
from .mediashare import AbstractMediashare, share_factory
from .queueprocessor import QueueProcessor
from .sync_regularcomplete import SyncRegularcomplete
from .types import Priority, PriorizedTask, SyncTaskDelete, SyncTaskUpdate, SyncTaskUpload
from .utils import get_remote_filepath

logger = logging.getLogger(__name__)


class Synchronizer(BasePlugin[SynchronizerConfig]):
    def __init__(self):
        super().__init__()

        self._config = SynchronizerConfig()
        self._queue_processors: list[QueueProcessor] = []
        self._regular_complete_sync: list[SyncRegularcomplete] = []
        self._shares: list[AbstractMediashare] = []

    @hookimpl
    def start(self):
        self.reset()

        if not self._config.common.enabled:
            logger.info("Synchronizer Plugin is disabled")
            return

        # consumes the queue and uploads/deletes/modifies remote filesystem according to the queue.
        for cfg in self._config.backends:
            if not cfg.enabled:
                continue

            queueprocessor = QueueProcessor(cfg.backend_config.connector)

            if cfg.enable_share_link:
                share = share_factory(cfg.backend_config, connector_factory.connector_factory(cfg.backend_config.connector))
                self._shares.append(share)

                dl_portal_local = share.downloadportal_file()
                if dl_portal_local:
                    # add to queue for later upload.
                    # this way if no internet the startup is not causing issues preventing the complete app from startup
                    logger.info(f"automatic update check of downloadportal to {queueprocessor} added.")
                    queueprocessor.put_to_queue(PriorizedTask(Priority.HIGH, SyncTaskUpdate(dl_portal_local, Path(dl_portal_local.name))))
                # else:
                #     logger.info(f"automatic update check of downloadportal to {queueprocessor} is disabled.")

            if cfg.enable_regular_sync:
                self._regular_complete_sync.append(
                    SyncRegularcomplete(
                        connector_factory.connector_factory(cfg.backend_config.connector),
                        queueprocessor,
                        Path("./media/"),
                    )
                )

            if cfg.enable_immediate_sync or cfg.enable_regular_sync:
                self._queue_processors.append(queueprocessor)

        for instance in self._queue_processors:
            instance.start()

        for instance in self._regular_complete_sync:
            instance.start()

    @hookimpl
    def stop(self):
        for instance in self._queue_processors:
            instance.stop()

        for instance in self._regular_complete_sync:
            instance.stop()

    def reset(self):
        self._queue_processors = []
        self._regular_complete_sync = []
        self._shares = []

    def _put_to_processors_queues(self, priorized_task: PriorizedTask):
        for queue_processor in self._queue_processors:
            queue_processor.put_to_queue(priorized_task)

    @hookimpl
    def get_stats(self) -> GenericStats | None:
        if self._config.common.enabled is False:
            # avoids display of an empty stats object in the admin dashboard
            return None

        out = GenericStats(id="hook-plugin-synchronizer", name="Synchronizer")

        for queue_processor in self._queue_processors:
            sqs = queue_processor._stats
            out.stats.append(
                SubList(
                    name=str(queue_processor),
                    val=[
                        SubStats("remaining", sqs.remaining_files),
                        SubStats("success", sqs.success),
                        SubStats("failed", sqs.fail),
                    ],
                )
            )

        for regular_complete_sync in self._regular_complete_sync:
            rcss = regular_complete_sync._stats

            out.stats.append(
                SubList(
                    name=str(regular_complete_sync),
                    val=[
                        SubStats("check_active", rcss.check_active, display=DisplayEnum.spinner),
                        SubStats("last_check_started", rcss.last_check_started.astimezone().strftime("%X") if rcss.last_check_started else None),
                        SubStats("last_duration", rcss.last_duration, unit="s"),
                        SubStats("next_check", rcss.next_check.astimezone().strftime("%X") if rcss.next_check else None),
                        SubStats("files_queued_last_check", rcss.files_queued_last_check),
                    ],
                )
            )

        return out

    @hookimpl
    def get_share_links(self, filepath_local: Path) -> list[str]:
        share_links: list[str] = []

        if not self._config.common.enable_share_links:
            logger.info("share link generation is disabled globally in synchronizer plugin")
            return []

        for instance in self._shares:
            filepath_remote = get_remote_filepath(filepath_local)
            share_link = instance.get_share_link(filepath_remote)
            if share_link:
                share_links.append(share_link)

        return share_links

    @hookimpl
    def collection_original_file_added(self, files: list[Path]):
        for file in files:
            self._put_to_processors_queues(PriorizedTask(Priority.LOW, SyncTaskUpload(file, get_remote_filepath(file))))

    @hookimpl
    def collection_files_added(self, files: list[Path]):
        for file in files:
            self._put_to_processors_queues(PriorizedTask(Priority.HIGH, SyncTaskUpload(file, get_remote_filepath(file))))

    @hookimpl
    def collection_files_updated(self, files: list[Path]):
        for file in files:
            self._put_to_processors_queues(PriorizedTask(Priority.HIGH, SyncTaskUpload(file, get_remote_filepath(file))))

    @hookimpl
    def collection_files_deleted(self, files: list[Path]):
        for file in files:
            self._put_to_processors_queues(PriorizedTask(Priority.LOW, SyncTaskDelete(get_remote_filepath(file))))
