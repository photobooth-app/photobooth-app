import logging
import threading
import time
from dataclasses import dataclass, field
from queue import Empty, PriorityQueue

from ...utils import rclone
from ...utils.resilientservice import ResilientService
from .config import RcloneRemoteConfig, SyncQueueConfig
from .types import PriorizedTask, SyncTaskDelete, SyncTaskUpdate, SyncTaskUpload, taskSyncType

logger = logging.getLogger(__name__)


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

    def update_on_rclone_event(self, event: dict):
        stats = event.get("stats")
        print()
        if stats:
            print(stats)


class SyncQueue(ResilientService):
    def __init__(self, config: SyncQueueConfig, rclone_config: RcloneRemoteConfig):
        super().__init__()

        self.__config: SyncQueueConfig = config
        self.__rclone_config: RcloneRemoteConfig = rclone_config
        self.__queue: PriorityQueue[PriorizedTask] = PriorityQueue[PriorizedTask]()
        self.__stats: Stats = Stats()

    def __str__(self):
        return f"Queue ({self.__queue})"

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def put_to_queue(self, task: PriorizedTask):
        if self._stop_event.is_set():
            # logger.info(f"{self} shutting down, ignored request to queue task {task}!") # don't log this on shutdown because its too much
            return

        self.__queue.put_nowait(task)
        self.__stats.add_remaining()

    def setup_resource(self): ...

    def teardown_resource(self):
        self.__queue = PriorityQueue[PriorizedTask]()  # clear to abort processing in service
        self.__stats = Stats()

    def run_service(self):
        last_print_time = 0
        print_interval = 5
        queue_timeout = 0.2  # wait until timout for a queue entry to process.

        while not self._stop_event.is_set():
            now = time.time()
            queue_size = self.__queue.qsize()

            if queue_size > 0 and now - last_print_time >= print_interval:
                logger.info(f"{self.__stats} - {self}")
                last_print_time = now

            try:
                priorizedTask = self.__queue.get(timeout=queue_timeout)

            except Empty:
                continue

            else:
                task = priorizedTask.task
                assert isinstance(task, taskSyncType)

                try:
                    if type(task) is SyncTaskUpload:
                        process = rclone.copy(
                            src_path=str(task.file_local),
                            dest_path=f"{self.__rclone_config.remote.rstrip(':')}:{self.__rclone_config.remote_base_dir.rstrip('/')}/{task.folder_remote}",
                            callback=self.__stats.update_on_rclone_event,
                        )
                        process.wait()
                    elif type(task) is SyncTaskUpdate:
                        process = rclone.copy(
                            src_path=str(task.file_local),
                            dest_path=f"{self.__rclone_config.remote.rstrip(':')}:{self.__rclone_config.remote_base_dir.rstrip('/')}/{task.folder_remote}",
                            callback=self.__stats.update_on_rclone_event,
                        )
                        process.wait()
                    elif type(task) is SyncTaskDelete:
                        rclone.delete(
                            f"{self.__rclone_config.remote.rstrip(':')}:{self.__rclone_config.remote_base_dir.rstrip('/')}/{task.file_remote}"
                        )
                    # else never as per typing

                except Exception as exc:
                    self.__stats.increment_fail()
                    logger.exception(exc)
                    logger.error(f"failed processing task {priorizedTask}, error {exc}")
                    # TODO: what if task failed? reinsert to sync queue?
                else:
                    self.__stats.increment_success()
                    # logger.info(f"successfully processed task {priorizedTask}")
                finally:
                    self.__queue.task_done()

        logger.info(f"left processing {self}")
