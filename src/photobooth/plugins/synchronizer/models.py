from dataclasses import dataclass
from pathlib import Path


@dataclass
class SyncTaskUpload:
    filepath_local: Path


@dataclass
class SyncTaskDelete:
    # despite removing remote file, we hand over the local path that is to delete.
    # the synchronizer/worker needs to find the remote counterpart on its own.
    filepath_local: Path
