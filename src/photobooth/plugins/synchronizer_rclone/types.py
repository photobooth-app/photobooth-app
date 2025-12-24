from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from pathlib import Path


@dataclass
class Stats:
    check_active: bool = False
    last_check_started: datetime | None = None  # datetime to convert .astimezone().strftime('%Y%m%d-%H%M%S')
    last_duration: float | None = None
    next_check: datetime | None = None
    files_queued_last_check: int = 0

    def update(self, record: dict):
        # receives updates from rclone via listener.
        ...


@dataclass
class SyncTaskUpload:
    """Upload without prior check if it exists or is outdated"""

    file_local: Path
    folder_remote: Path

    def __str__(self):
        return self.file_local.name


@dataclass
class SyncTaskUpdate(SyncTaskUpload):
    """Update if not existing or file size different only. Prior upload checking if is same."""


@dataclass
class SyncTaskDelete:
    """Delete from remote"""

    file_remote: Path

    def __str__(self):
        return self.file_remote.name


taskSyncType = SyncTaskUpload | SyncTaskUpdate | SyncTaskDelete


class Priority(IntEnum):
    HIGH = 1  # high for immediate syncs
    LOW = 2  # low for regular syncs


@dataclass(order=True)
class PriorizedTask:
    priority: Priority
    task: taskSyncType = field(compare=False)

    def __str__(self):
        return f"{self.task} - {self.priority.name} priority)"
