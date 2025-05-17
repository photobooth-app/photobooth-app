import logging
from itertools import count
from pathlib import Path
from queue import Empty

from ...utils.resilientservice import ResilientService
from .backends.base import BaseBackend
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


class SyncWorker(ResilientService):
    def __init__(self, sync_backend):
        super().__init__()

        self._sync_backend: BaseBackend = sync_backend  # FTPClient, ... derived from BaseClient.
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
        self._sync_backend.connect()

    def teardown_resource(self):
        self._sync_backend.disconnect()

    def run_service(self):
        assert self._sync_backend
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
                        logger.debug(f"No files to sync since {idle_mode_timeout}s, disconnecting from server, waiting in idle mode")
                        self._idle_mode = True
                        self._sync_backend.disconnect()

                continue
            else:
                self._idle_since_seconds = 0
                task = priotask[2]

                # quit on shutdown.
                if task is None:
                    break

                if self._idle_mode:
                    logger.debug("Resume from idle mode, connecting to server")
                    self._sync_backend.connect()
                    self._idle_mode = False

                self._run_task(task)

    def _run_task(self, task: SyncTaskUpload | SyncTaskDelete):
        if isinstance(task, SyncTaskUpload):
            self._sync_backend.do_upload(task.filepath_local, get_remote_filepath(task.filepath_local))
        elif isinstance(task, SyncTaskDelete):
            self._sync_backend.do_delete_remote(get_remote_filepath(task.filepath_local))
        # else:
        #     raise RuntimeError()
        # TODO: what if task failed? reinsert to sync queue?

        logger.info(f"sync job finished: {task}")
