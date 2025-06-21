import logging
from queue import Empty

from ...utils.resilientservice import ResilientService
from .connectors.abstractconnector import AbstractConnector
from .models import SyncTaskDelete, SyncTaskUpload
from .types import queueSyncType, taskSyncType

logger = logging.getLogger(__name__)


class SyncQueue(ResilientService):
    def __init__(self, connector: AbstractConnector):
        super().__init__()

        self._connector: AbstractConnector = connector

        # start with fresh queue
        self._queue: queueSyncType = queueSyncType()

    def __str__(self):
        return f"{self.__class__.__name__}: {self._connector}"

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def put_to_queue(self, task: taskSyncType):
        self._queue.put_nowait(task)

    def setup_resource(self):
        self._connector.connect()

    def teardown_resource(self):
        self._connector.disconnect()

    def run_service(self):
        assert self._connector
        assert self._queue
        queue_timeout = 0.2  # wait until timout for a queue entry to process.

        while not self._stop_event.is_set():
            # queue_size = self._queue.qsize()
            # if queue_size > 0:
            #     print(f"noch {queue_size} zu verarbeiten.")

            try:
                task = self._queue.get(timeout=queue_timeout)
            except Empty:
                continue
            else:
                # quit on shutdown.
                if task is None:
                    break

                if isinstance(task, SyncTaskUpload):
                    self._connector.do_upload(task.filepath_local, task.filepath_remote)
                elif isinstance(task, SyncTaskDelete):
                    self._connector.do_delete_remote(task.filepath_remote)
                # else:
                #     raise RuntimeError()
                # TODO: what if task failed? reinsert to sync queue?

                logger.info(f"sync job finished: {task}")
