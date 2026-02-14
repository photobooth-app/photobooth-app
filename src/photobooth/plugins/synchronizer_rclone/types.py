from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import TypeAlias


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

    file: Path

    def __str__(self):
        return str(self.file.absolute())


@dataclass
class TaskDelete:
    """Delete from remote"""

    file: Path

    def __str__(self):
        return str(self.file.absolute())


TaskSyncType: TypeAlias = TaskCopy | TaskDelete
