import logging
from pathlib import Path

from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import SynchronizerConfig
from .connectors import connector_factory
from .models import SyncTaskDelete, SyncTaskUpload
from .share import AbstractMediashare, share_factory
from .sync_queue import SyncQueue
from .sync_regularcomplete import SyncRegularcomplete
from .types import taskSyncType
from .utils import get_remote_filepath

logger = logging.getLogger(__name__)


class Synchronizer(BasePlugin[SynchronizerConfig]):
    def __init__(self):
        super().__init__()

        self._config: SynchronizerConfig = SynchronizerConfig()
        self._sync_queue: list[SyncQueue] = []
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

            connector = connector_factory.connector_factory(cfg.backend_config.connector)
            # connector for syncqueue is reused - could be a new one also but not needed actually.
            share = share_factory(cfg.backend_config, connector)
            share.update_downloadportal()
            self._shares.append(share)

            # finally lets hold a reference here for future disptaching.
            self._sync_queue.append(SyncQueue(connector))

            if cfg.enable_regular_sync:
                self._regular_complete_sync.append(
                    SyncRegularcomplete(
                        connector_factory.connector_factory(cfg.backend_config.connector),
                        Path("./media/"),
                    )
                )

        for sync_queue in self._sync_queue:
            sync_queue.start()

        for regular_complete_sync in self._regular_complete_sync:
            regular_complete_sync.start()

    @hookimpl
    def stop(self):
        """To stop the resilient service"""

        # stop first, so following None (stop-NOW indicator) will be effective
        for sync_queue in self._sync_queue:
            sync_queue.stop()

        for regular_complete_sync in self._regular_complete_sync:
            regular_complete_sync.stop()

        # TODO: because stop joins, this does not have any effect actually.
        self._put_to_workers_queues(None)

    def reset(self):
        self._sync_queue = []
        self._shares = []
        self._regular_complete_sync = []

    def _put_to_workers_queues(self, tasks: taskSyncType):
        # map(lambda backend_worker: backend_worker.put_to_queue(tasks), self._backend_workers)
        for sync_queue in self._sync_queue:
            sync_queue.put_to_queue(tasks)

    def stats(self):
        print("here we can emit stats for the admin dashboard, maybe?")

    @hookimpl
    def get_share_links(self, filepath_local: Path) -> list[str]:
        share_links: list[str] = []

        if not self._config.common.enable_share_links:
            logger.info("share link generation is disabled globally in synchronizer plugin")
            return []

        for worker in self._shares:
            filepath_remote = get_remote_filepath(filepath_local)
            share_link = worker.get_share_link(filepath_remote)
            if share_link:
                share_links.append(share_link)

        return share_links

    @hookimpl
    def collection_original_file_added(self, files: list[Path]):
        logger.info(f"SYNC File ORIGINAL ADDED NOTE {files}")
        for file in files:
            self._put_to_workers_queues(SyncTaskUpload(file, get_remote_filepath(file)))

    @hookimpl
    def collection_files_added(self, files: list[Path]):
        logger.info(f"SYNC File added NOTE {files}")
        for file in files:
            self._put_to_workers_queues(SyncTaskUpload(file, get_remote_filepath(file)))

    @hookimpl
    def collection_files_updated(self, files: list[Path]):
        logger.info(f"SYNC File updated NOTE {files}")
        for file in files:
            self._put_to_workers_queues(SyncTaskUpload(file, get_remote_filepath(file)))

    @hookimpl
    def collection_files_deleted(self, files: list[Path]):
        logger.info(f"SYNC File delete NOTE {files}")
        for file in files:
            self._put_to_workers_queues(SyncTaskDelete(get_remote_filepath(file)))
