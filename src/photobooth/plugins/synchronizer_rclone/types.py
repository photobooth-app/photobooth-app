from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypeAlias


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
class TaskCopy:
    """Upload without prior check if it exists or is outdated"""

    file_local: Path
    file_remote: Path

    def __str__(self):
        return self.file_local.name


@dataclass
class TaskDelete:
    """Delete from remote"""

    file_remote: Path

    def __str__(self):
        return self.file_remote.name


TaskSyncType: TypeAlias = TaskCopy | TaskDelete

# taskSyncType: TypeAlias = TaskCopy | TaskDelete
# taskSyncType:type = TaskCopy | TaskDelete
