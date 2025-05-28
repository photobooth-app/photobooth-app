import logging
import shutil
from pathlib import Path

from ..config import FilesystemBackendConfig
from .base import BaseBackend

logger = logging.getLogger(__name__)


class FilesystemBackend(BaseBackend):
    def __init__(self, config: FilesystemBackendConfig):
        super().__init__()

        self._target_dir: Path | None = config.target_dir

    def connect(self):
        if not self._target_dir:
            raise ValueError("no target directory given!")

        if self._target_dir.exists() and not self._target_dir.is_dir():
            raise ValueError(f"target_dir {self._target_dir} exists but is not a directory. The target needs to be a directory.")

        if not self._target_dir.exists():
            print("target dir not existing, creating")
            self._target_dir.mkdir(parents=True, exist_ok=True)

        logger.info("filesystem ready to sync")

    def disconnect(self):
        pass

    def is_connected(self):
        if not self._target_dir:  # None or ""
            return False

        return self._target_dir.is_dir()

    def get_remote_samefile(self, local_path: Path, remote_path: Path) -> bool:
        assert self._target_dir
        try:
            return local_path.samefile(self._target_dir.joinpath(remote_path))
        except Exception as exc:
            print(exc)
            return False

    def do_upload(self, local_path: Path, remote_path: Path):
        assert self._target_dir

        if not self._target_dir.joinpath(remote_path).parent.is_dir():
            print("target dir not existing, creating")
            self._target_dir.joinpath(remote_path).parent.mkdir(parents=True, exist_ok=True)

        if self.get_remote_samefile(local_path, remote_path):
            print("samefile, no copy")
            return

        print("copy file")
        shutil.copy2(local_path, self._target_dir.joinpath(remote_path))

    def do_delete_remote(self, remote_path: Path):
        assert self._target_dir

        print("delete file")
        self._target_dir.joinpath(remote_path).unlink(missing_ok=True)
