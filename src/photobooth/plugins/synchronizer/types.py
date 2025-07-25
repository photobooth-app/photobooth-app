from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path


@dataclass
class SyncTaskUpload:
    filepath_local: Path
    filepath_remote: Path

    def __str__(self):
        return self.filepath_local.name


@dataclass
class SyncTaskDelete:
    filepath_remote: Path

    def __str__(self):
        return self.filepath_remote.name


taskSyncType = SyncTaskUpload | SyncTaskDelete


class Priority(IntEnum):
    HIGH = 1  # high for immediate syncs
    LOW = 2  # low for regular syncs


@dataclass(order=True)
class PriorizedTask:
    priority: Priority
    task: taskSyncType = field(compare=False)

    def __str__(self):
        return f"{self.task} - {self.priority.name} priority)"
