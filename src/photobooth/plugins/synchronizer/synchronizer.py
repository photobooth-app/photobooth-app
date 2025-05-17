import logging
from itertools import count
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from .. import hookimpl
from ..base_plugin import BasePlugin
from .backends.filesystem import FilesystemBackend
from .backends.ftp import FtpBackend
from .config import SynchronizerConfig
from .models import SyncTaskDelete, SyncTaskUpload
from .types import priorityTaskSyncType
from .worker import SyncWorker

logger = logging.getLogger(__name__)
counter = count()  # tie-breaker, always incr on put to queue so the following dataclass is not compared


class Synchronizer(BasePlugin[SynchronizerConfig]):
    def __init__(self):
        super().__init__()

        self._config: SynchronizerConfig = SynchronizerConfig()
        # self._local_root_dir: Path = Path("./media/")

        self._sync_workers: list[SyncWorker] = []

    @hookimpl
    def start(self):
        if not self._config.common.enabled:
            logger.info("Synchronizer Plugin is disabled")
            return

        # consumes the queue and uploads/deletes/modifies remote filesystem according to the queue.
        for backendConfig in self._config.backends:
            if not backendConfig.enabled:
                continue

            if backendConfig.backend_config.backend_type == "filesystem":
                self._sync_workers.append(SyncWorker(FilesystemBackend(backendConfig.backend_config)))
            elif backendConfig.backend_config.backend_type == "ftp":
                self._sync_workers.append(SyncWorker(FtpBackend(backendConfig.backend_config)))
            # else not gonna happen because typed literals...

        for sync_worker in self._sync_workers:
            sync_worker.start()

    @hookimpl
    def stop(self):
        """To stop the resilient service"""

        for sync_worker in self._sync_workers:
            self._put_to_workers_queues((0, next(counter), None))  # lowest (==highest) priority for None to stop processing.
            sync_worker.stop()

    def _put_to_workers_queues(self, tasks: priorityTaskSyncType):
        for sync_worker in self._sync_workers:
            sync_worker.put_to_queue(tasks)

    def stats(self):
        print("here we can emit stats for the admin dashboard, maybe?")

    @hookimpl
    def get_share_link(self, identifier: UUID, filename: str):
        if not self._config.common.enable_share_link:
            print("share link for qr code disabled")
            return

        logger.info(f"GETTING SHARE LINK {identifier} {filename}")

        download_portal_url = f"{self._config.common.share_url.rstrip('/')}/#/?url="

        mediaitem_url = self._config.common.media_url
        mediaitem_url = mediaitem_url.replace("{filename}", filename)
        mediaitem_url = mediaitem_url.replace("{identifier}", str(identifier))

        return download_portal_url + quote(mediaitem_url, safe="")

    @hookimpl
    def collection_original_file_added(self, files: list[Path]):
        logger.info(f"SYNC File ORIGINAL ADDED NOTE {files}")
        for file in files:
            self._put_to_workers_queues((20, next(counter), SyncTaskUpload(file)))

    @hookimpl
    def collection_files_added(self, files: list[Path]):
        logger.info(f"SYNC File added NOTE {files}")
        for file in files:
            self._put_to_workers_queues((10, next(counter), SyncTaskUpload(file)))

    @hookimpl
    def collection_files_updated(self, files: list[Path]):
        logger.info(f"SYNC File updated NOTE {files}")
        for file in files:
            self._put_to_workers_queues((10, next(counter), SyncTaskUpload(file)))

    @hookimpl
    def collection_files_deleted(self, files: list[Path]):
        logger.info(f"SYNC File delete NOTE {files}")
        for file in files:
            self._put_to_workers_queues((15, next(counter), SyncTaskDelete(file)))


# class RegularCompleteSync(ResilientService):
#     def __init__(self, sync_backend, queue, local_root_dir: Path):
#         super().__init__()

#         self._sync_backend: BaseProtocolClient = sync_backend  # FTPClient, ... derived from BaseClient.
#         self._queue: priorityQueueSyncType = queue
#         self._local_root_dir: Path = local_root_dir

#         # start resilient service activates below functions
#         self.start()

#     def start(self):
#         super().start()

#     def stop(self):
#         super().stop()

#     def setup_resource(self):
#         self._sync_backend.connect()

#     def teardown_resource(self):
#         self._sync_backend.disconnect()

#     def run_service(self):
#         assert self._sync_backend
#         assert self._queue

#         while not self._stop_event.is_set():
#             print("Starte Initial-datei sync...")

#             for local_path in Path(self._local_root_dir).glob("**/*.*"):
#                 # if self._stop_event.is_set():
#                 #     print("stop queueuing because shutdown already requested.")
#                 #     return

#                 try:
#                     remote_path = get_remote_filepath(self._local_root_dir, local_path)
#                     size = self._sync_backend.get_remote_filesize(remote_path)
#                     local_size = os.path.getsize(local_path)

#                     if size != local_size:
#                         self._queue.put_nowait((50, next(counter), SyncTaskUpload(local_path, remote_path)))
#                         print(f"queueud for upload: {local_path}")

#                 except Exception as e:
#                     print(f"Fehler bei verarbeitung von {local_path}: {e}")
#                     raise e

#             print(get_folder_list_cached.cache_info())

#             print("Initial-Synchronisation abgeschlossen.")

#             # self.stop()
#             # TODO: stop from within thread is not allowed (deadlock!) need to figure out a way to have a one-time living service.
