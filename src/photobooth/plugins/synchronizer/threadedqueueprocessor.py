import logging
import threading
import time
from dataclasses import dataclass, field
from queue import Empty
from typing import Generic, TypeVar

from ...utils.resilientservice import ResilientService
from .config import ConnectorConfig
from .connectors.abstractconnector import AbstractConnector
from .connectors.connector_factory import connector_factory
from .types import Priority, PriorizedTask, SyncTaskDelete, SyncTaskUpload, queueSyncType, taskSyncType

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=ConnectorConfig)


@dataclass
class Stats:
    success: int = 0
    fail: int = 0
    remaining_files: int = 0

    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def increment_success(self):
        with self.lock:
            self.success += 1
            self.remaining_files -= 1

    def increment_fail(self):
        with self.lock:
            self.fail += 1
            self.remaining_files -= 1

    def add_remaining(self):
        with self.lock:
            self.remaining_files += 1

    def __str__(self):
        with self.lock:
            return f"Stats: Success: {self.success:3d} Failed: {self.fail:3d}  Remaining Files: {self.remaining_files:3d}"

    def to_dict(self):
        return {
            "success": self.success,
            "fail": self.fail,
            "remaining_files": self.remaining_files,
        }


class ThreadedQueueProcessor(ResilientService, Generic[T]):
    def __init__(self, config: T):
        super().__init__()

        self._connector: AbstractConnector = connector_factory(config)  # TODO: multiple, later... lets start with resilientservice
        self._queue: queueSyncType = queueSyncType()
        self._stats: Stats = Stats()

    def __str__(self):
        return f"{self.__class__.__name__}: {self._connector}"

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def put_to_queue(self, task: PriorizedTask):
        if self._stop_event.is_set():
            logger.info(f"{self} shutting down, ignored request to queue task {task}!")
            return

        self._queue.put_nowait(task)
        self._stats.add_remaining()

    def setup_resource(self):
        self._stats: Stats = Stats()
        self._connector.connect()

    def teardown_resource(self):
        self._queue = queueSyncType()  # clear to abort processing in service
        self._queue.put_nowait(PriorizedTask(Priority.SHUTDOWN, None))
        self._connector.disconnect()

    def run_service(self):
        last_print_time = 0
        print_interval = 5
        queue_timeout = 0.2  # wait until timout for a queue entry to process.

        while not self._stop_event.is_set():
            now = time.time()
            queue_size = self._queue.qsize()

            if queue_size > 0 and now - last_print_time >= print_interval:
                logger.info(f"{self._stats} - {self}")
                last_print_time = now

            try:
                priorizedTask = self._queue.get(timeout=queue_timeout)

            except Empty:
                continue
            else:
                task = priorizedTask.task
                assert isinstance(task, taskSyncType)

                # quit on shutdown.
                if task is None or self._stop_event.is_set():
                    logger.info(f"stop processing on shutdown {self}")
                    break

                try:
                    if isinstance(task, SyncTaskUpload):
                        self._connector.do_upload(task.filepath_local, task.filepath_remote)
                    elif isinstance(task, SyncTaskDelete):
                        self._connector.do_delete_remote(task.filepath_remote)
                    else:
                        raise RuntimeError(f"Error processing unknown task: {priorizedTask}")

                except Exception as exc:
                    self._stats.increment_fail()
                    logger.error(f"failed processing task {priorizedTask}, error {exc}")
                    # TODO: what if task failed? reinsert to sync queue?
                else:
                    self._stats.increment_success()
                    # logger.info(f"successfully processed task {priorizedTask}")
