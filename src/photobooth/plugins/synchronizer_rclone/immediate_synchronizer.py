import itertools
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, PriorityQueue

from rclone_api.api import RcloneApi

from photobooth.plugins.synchronizer_rclone.utils import get_corresponding_remote_file

from .config import RemoteConfig
from .types import CopyOperation, DeleteOperation, JobResult, JobStatus, OperationTypes, TaskCopy, TaskDelete, TaskSyncType

logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    pending: int
    transferring: int
    finished: int
    failed: int

    @property
    def total(self) -> int:
        return self.pending + self.transferring + self.finished + self.failed


@dataclass(order=True)
class PrioritizedJob:
    priority: int
    job_id: int = field(compare=False)
    operation: OperationTypes = field(compare=False)

    def __str__(self):
        return f"{self.operation} @prio {self.priority:>2}"


class ThreadedImmediateSyncPipeline:
    def __init__(self, rclone: RcloneApi, remotes: list[RemoteConfig], max_concurrency: int = 2, max_retries: int = 3, retry_delay: float = 5.0):
        self.rclone = rclone
        self.remotes = remotes
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.queue: PriorityQueue[PrioritizedJob] = PriorityQueue()

        self.results: dict[int, JobResult] = {}
        self._job_counter = itertools.count()

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._workers = [threading.Thread(target=self._worker_loop, name=f"rclone-immediate-worker-{i}", daemon=True) for i in range(max_concurrency)]

        for w in self._workers:
            w.start()

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------
    def stop(self):
        self._stop_event.set()

        for w in self._workers:
            w.join()

    def reset(self):
        self.results = {}

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> PipelineStats:
        with self._lock:
            return PipelineStats(
                pending=sum(1 for r in self.results.values() if r.status == JobStatus.PENDING),
                transferring=sum(1 for r in self.results.values() if r.status == JobStatus.TRANSFERRING),
                finished=sum(1 for r in self.results.values() if r.status == JobStatus.FINISHED),
                failed=sum(1 for r in self.results.values() if r.status == JobStatus.FAILED),
            )

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------
    def submit(self, task: TaskSyncType, priority: int = 10):

        for r in self.remotes:
            # translate task to rclone operation for all remotes listed here
            if isinstance(task, TaskCopy):
                op = CopyOperation(
                    str(Path.cwd().absolute()), f"{task.file}", r.name, Path(r.subdir, get_corresponding_remote_file(task.file)).as_posix()
                )
            elif isinstance(task, TaskDelete):
                op = DeleteOperation(r.name, Path(r.subdir, get_corresponding_remote_file(task.file)).as_posix())
            # else never as per typing

            job_id = next(self._job_counter)
            job = PrioritizedJob(priority=priority, job_id=job_id, operation=op)

            with self._lock:
                self.results[job_id] = JobResult(JobStatus.PENDING, 0, None)

            self.queue.put(job)

    # --------------------------------------------------------
    # Worker Loop
    # --------------------------------------------------------
    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                job = self.queue.get(timeout=0.1)
            except Empty:
                continue

            attempts = 0
            while attempts < self.max_retries and not self._stop_event.is_set():
                attempts += 1

                with self._lock:
                    self.results[job.job_id] = JobResult(JobStatus.TRANSFERRING, attempts, None)

                op = job.operation

                try:
                    if isinstance(op, CopyOperation):
                        self.rclone.copyfile(op.src_fs, op.src_remote, op.dst_fs, op.dst_remote)
                    elif isinstance(op, DeleteOperation):
                        self.rclone.deletefile(op.dst_fs, op.dst_remote)
                    else:
                        raise RuntimeError(f"Unsupported operation type: {type(op)!r}")

                    with self._lock:
                        self.results[job.job_id] = JobResult(JobStatus.FINISHED, attempts, None)

                    logger.debug(f"immediate sync finished: {job}")

                    break  # <-- job finished successfully, quit retry loop

                except Exception as exc:
                    with self._lock:
                        self.results[job.job_id] = JobResult(JobStatus.TRANSFERRING, attempts, str(exc))

                    time.sleep(self.retry_delay + random.uniform(0, 0.5))

            # at this point all failed...
            with self._lock:
                self.results[job.job_id] = JobResult(JobStatus.FAILED, attempts, "max retries exceeded")
