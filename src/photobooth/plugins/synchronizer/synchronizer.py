import logging
from pathlib import Path

from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import SynchronizerConfig
from .connectors import connector_factory
from .models import SyncTaskDelete, SyncTaskUpload
from .share import AbstractMediashare, share_factory
from .sync_queue import SyncQueue
from .types import taskSyncType

logger = logging.getLogger(__name__)


class Synchronizer(BasePlugin[SynchronizerConfig]):
    def __init__(self):
        super().__init__()

        self._config: SynchronizerConfig = SynchronizerConfig()
        self._backend_workers: list[SyncQueue] = []
        self._shares: list[AbstractMediashare] = []

    @hookimpl
    def start(self):
        self.reset()

        if not self._config.common.enabled:
            logger.info("Synchronizer Plugin is disabled")
            return

        # consumes the queue and uploads/deletes/modifies remote filesystem according to the queue.
        for backendConfig in self._config.backends:
            if not backendConfig.enabled:
                continue

            connector = connector_factory.connector_factory(backendConfig.backend_config.connector)
            # connector for syncqueue is reused - could be a new one also but not needed actually.
            share = share_factory(backendConfig.backend_config, connector)
            share.update_downloadportal()

            # finally lets hold a reference here for future disptaching.
            self._backend_workers.append(SyncQueue(connector))
            self._shares.append(share)

        for backend_worker in self._backend_workers:
            backend_worker.start()

    @hookimpl
    def stop(self):
        """To stop the resilient service"""

        # stop first, so following None (stop-NOW indicator) will be effective
        for backend_worker in self._backend_workers:
            backend_worker.stop()

        self._put_to_workers_queues(None)

    def reset(self):
        self._backend_workers = []
        self._shares = []

    def _put_to_workers_queues(self, tasks: taskSyncType):
        # map(lambda backend_worker: backend_worker.put_to_queue(tasks), self._backend_workers)
        for sync_worker in self._backend_workers:
            sync_worker.put_to_queue(tasks)

    def stats(self):
        print("here we can emit stats for the admin dashboard, maybe?")

    @hookimpl
    def get_share_links(self, filepath_local: Path) -> list[str]:
        share_links: list[str] = []

        if not self._config.common.enable_share_links:
            logger.info("share link generation is disabled globally in synchronizer plugin")
            return []

        for worker in self._shares:
            filepath_remote = self.get_remote_filepath(filepath_local)
            share_link = worker.get_share_link(filepath_remote)
            if share_link:
                share_links.append(share_link)

        return share_links

    @hookimpl
    def collection_original_file_added(self, files: list[Path]):
        logger.info(f"SYNC File ORIGINAL ADDED NOTE {files}")
        for file in files:
            self._put_to_workers_queues(SyncTaskUpload(file, self.get_remote_filepath(file)))

    @hookimpl
    def collection_files_added(self, files: list[Path]):
        logger.info(f"SYNC File added NOTE {files}")
        for file in files:
            self._put_to_workers_queues(SyncTaskUpload(file, self.get_remote_filepath(file)))

    @hookimpl
    def collection_files_updated(self, files: list[Path]):
        logger.info(f"SYNC File updated NOTE {files}")
        for file in files:
            self._put_to_workers_queues(SyncTaskUpload(file, self.get_remote_filepath(file)))

    @hookimpl
    def collection_files_deleted(self, files: list[Path]):
        logger.info(f"SYNC File delete NOTE {files}")
        for file in files:
            self._put_to_workers_queues(SyncTaskDelete(self.get_remote_filepath(file)))

    @staticmethod
    def get_remote_filepath(local_filepath: Path, local_root_dir: Path = Path("./media/")) -> Path:
        try:
            remote_path = local_filepath.relative_to(local_root_dir)
        except ValueError as exc:
            raise ValueError(f"file {local_filepath} needs to be below root dir {local_root_dir}.") from exc

        logger.info(f"{local_filepath} maps to {remote_path}")

        return remote_path
