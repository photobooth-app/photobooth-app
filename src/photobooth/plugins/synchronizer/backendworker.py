import logging
from itertools import count
from pathlib import Path
from queue import Empty
from urllib.parse import quote

from ...utils.resilientservice import ResilientService
from .config import FilesystemBackendConfig, FtpBackendConfig, NextcloudBackendConfig
from .connectors.filesystem import FilesystemConnector
from .connectors.ftp import FtpConnector
from .connectors.nextcloud import NextcloudConnector
from .models import SyncTaskDelete, SyncTaskUpload
from .types import priorityQueueSyncType, priorityTaskSyncType

logger = logging.getLogger(__name__)
counter = count()  # tie-breaker, always incr on put to queue so the following dataclass is not compared


def get_remote_filepath(local_filepath: Path, local_root_dir: Path = Path("./media/")) -> Path:
    try:
        remote_path = local_filepath.relative_to(local_root_dir)
    except ValueError as exc:
        raise ValueError(f"file {local_filepath} needs to be below root dir {local_root_dir}.") from exc

    logger.info(f"{local_filepath} maps to {remote_path}")

    return remote_path


class BackendWorker(ResilientService):
    def __init__(self, backend_config: FilesystemBackendConfig | FtpBackendConfig | NextcloudBackendConfig):
        super().__init__()

        self._config = backend_config

        if backend_config.backend_type == "filesystem":
            self._connector = FilesystemConnector(backend_config.connector)
        elif backend_config.backend_type == "ftp":
            self._connector = FtpConnector(backend_config.connector)
        elif backend_config.backend_type == "nextcloud":
            self._connector = NextcloudConnector(backend_config.connector)
        # else not gonna happen because typed literals...

        # start with fresh queue
        self._queue: priorityQueueSyncType = priorityQueueSyncType()

        self._idle_since_seconds: int = 0
        self._idle_mode: bool = False

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def put_to_queue(self, task: priorityTaskSyncType):
        self._queue.put_nowait(task)

    def setup_resource(self):
        self._connector.connect()

    def teardown_resource(self):
        self._connector.disconnect()

    def run_service(self):
        assert self._connector
        assert self._queue
        queue_timeout = 1  # wait until timout for a queue entry to process.
        idle_mode_timeout = 30  # after timeout disconnect and be in idle mode.

        while not self._stop_event.is_set():
            # queue_size = self._queue.qsize()
            # if queue_size > 0:
            #     print(f"noch {queue_size} zu verarbeiten.")

            try:
                priotask = self._queue.get(timeout=queue_timeout)
            except Empty:
                if not self._idle_mode:
                    self._idle_since_seconds += queue_timeout
                    if self._idle_since_seconds >= idle_mode_timeout:
                        logger.debug(f"No files to sync since {idle_mode_timeout}s, disconnecting from {self._connector}, waiting in idle mode")
                        self._idle_mode = True
                        self._connector.disconnect()

                continue
            else:
                self._idle_since_seconds = 0
                task = priotask[2]

                # quit on shutdown.
                if task is None:
                    break

                if self._idle_mode:
                    logger.debug(f"Resume from idle mode, connecting to server {self._connector}")
                    self._connector.connect()
                    self._idle_mode = False

                self._run_task(task)

    def _run_task(self, task: SyncTaskUpload | SyncTaskDelete):
        if isinstance(task, SyncTaskUpload):
            self._connector.do_upload(task.filepath_local, get_remote_filepath(task.filepath_local))
        elif isinstance(task, SyncTaskDelete):
            self._connector.do_delete_remote(get_remote_filepath(task.filepath_local))
        # else:
        #     raise RuntimeError()
        # TODO: what if task failed? reinsert to sync queue?

        logger.info(f"sync job finished: {task}")

    def get_share_link(self, filepath_local: Path) -> str | None:
        if not self._config.share.enable_share_link:
            logger.info("generating share links in synchronizer plugin is disabled for this backend")
            return None

        mediaitem_url = self.get_remote_mediaitem_link(filepath_local)
        if not mediaitem_url:
            logger.error("cannot share because there is no URL available for the media file provided by the connector")
            return None

        if self._config.share.downloadportal_url:
            downloadportal_url = f"{self._config.share.downloadportal_url.rstrip('/')}/#/?url="
            mediaitem_url_safe = quote(mediaitem_url, safe="")
            out = downloadportal_url + mediaitem_url_safe
        else:
            out = mediaitem_url

        logger.info(f"share link created for {filepath_local}: {out}")

        return out

    def get_remote_mediaitem_link(self, filepath_local: Path) -> str | None:
        return self._connector.mediaitem_link(get_remote_filepath(filepath_local))
