from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import TypeAlias

# ------------------------------------------------------------
# Regular Sync
# ------------------------------------------------------------


@dataclass
class Stats:
    last_check_started: datetime | None = None  # datetime to convert .astimezone().strftime('%Y%m%d-%H%M%S')
    next_check: datetime | None = None


# ------------------------------------------------------------
# Immediate Sync
# ------------------------------------------------------------


class JobStatus(Enum):
    PENDING = auto()
    TRANSFERRING = auto()
    FINISHED = auto()
    FAILED = auto()


@dataclass
class JobResult:
    status: JobStatus
    attempts: int
    error: str | None


@dataclass
class CopyOperation:
    src_fs: str
    src_remote: str
    dst_fs: str
    dst_remote: str

    def __str__(self):
        return f"{self.__class__.__name__}: {self.dst_fs}{self.dst_remote}"


@dataclass
class DeleteOperation:
    dst_fs: str
    dst_remote: str

    def __str__(self):
        return f"{self.__class__.__name__}: {self.dst_fs}{self.dst_remote}"


OperationTypes: TypeAlias = CopyOperation | DeleteOperation


@dataclass
class TaskCopy:
    """Copy to remove, update if needed."""

    file_local: Path
    file_remote: Path

    def __str__(self):
        return str(self.file_local.absolute())


@dataclass
class TaskDelete:
    """Delete from remote"""

    file_remote: Path

    def __str__(self):
        return str(self.file_remote.absolute())


TaskSyncType: TypeAlias = TaskCopy | TaskDelete
