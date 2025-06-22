import logging
from pathlib import Path

from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import SynchronizerConfig
from .connectors import connector_factory
from .share import AbstractMediashare, share_factory
from .sync_regularcomplete import SyncRegularcomplete
from .threadedqueueprocessor import ThreadedQueueProcessor
from .types import Priority, PriorizedTask, SyncTaskDelete, SyncTaskUpload
from .utils import get_remote_filepath

logger = logging.getLogger(__name__)


class Synchronizer(BasePlugin[SynchronizerConfig]):
    def __init__(self):
        super().__init__()

        self._config: SynchronizerConfig = SynchronizerConfig()
        self._sync_queue: list[ThreadedQueueProcessor] = []
        self._shares: list[AbstractMediashare] = []
        self._regular_complete_sync: list[SyncRegularcomplete] = []

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

            threadedqueueprocessor = ThreadedQueueProcessor(cfg.backend_config.connector)

            if cfg.enable_share_link:
                share = share_factory(cfg.backend_config, connector_factory.connector_factory(cfg.backend_config.connector))
                share.update_downloadportal()
                self._shares.append(share)

            if cfg.enable_regular_sync:
                self._regular_complete_sync.append(
                    SyncRegularcomplete(
                        connector_factory.connector_factory(cfg.backend_config.connector),
                        threadedqueueprocessor,
                        Path("./media/"),
                    )
                )

            if cfg.enable_immediate_sync:
                self._sync_queue.append(threadedqueueprocessor)

        for instance in self._sync_queue:
            instance.start()

        for instance in self._regular_complete_sync:
            instance.start()

    @hookimpl
    def stop(self):
        for instance in self._sync_queue:
            instance.stop()

        for instance in self._regular_complete_sync:
            instance.stop()

    def reset(self):
        self._sync_queue = []
        self._shares = []
        self._regular_complete_sync = []

    def _put_to_workers_queues(self, priorized_task: PriorizedTask):
        for sync_queue in self._sync_queue:
            sync_queue.put_to_queue(priorized_task)

    def stats(self):
        out = []
        for sync_queue in self._sync_queue:
            out.append(sync_queue._stats)
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
            self._put_to_workers_queues(PriorizedTask(Priority.LOW, SyncTaskUpload(file, get_remote_filepath(file))))

    @hookimpl
    def collection_files_added(self, files: list[Path]):
        for file in files:
            self._put_to_workers_queues(PriorizedTask(Priority.HIGH, SyncTaskUpload(file, get_remote_filepath(file))))

    @hookimpl
    def collection_files_updated(self, files: list[Path]):
        for file in files:
            self._put_to_workers_queues(PriorizedTask(Priority.HIGH, SyncTaskUpload(file, get_remote_filepath(file))))

    @hookimpl
    def collection_files_deleted(self, files: list[Path]):
        for file in files:
            self._put_to_workers_queues(PriorizedTask(Priority.LOW, SyncTaskDelete(get_remote_filepath(file))))
