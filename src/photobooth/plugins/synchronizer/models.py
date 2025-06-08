from dataclasses import dataclass
from pathlib import Path


@dataclass
class SyncTaskUpload:
    filepath_local: Path
    filepath_remote: Path


@dataclass
class SyncTaskDelete:
    filepath_remote: Path
