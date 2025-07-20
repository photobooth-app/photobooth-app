import logging
import shutil
from pathlib import Path

from ..config import FilesystemConnectorConfig
from .abstractconnector import AbstractConnector

logger = logging.getLogger(__name__)


class FilesystemConnector(AbstractConnector):
    def __init__(self, config: FilesystemConnectorConfig):
        super().__init__(config)

        self._target_dir: Path | None = config.target_dir

    def __str__(self):
        return f"{self.__class__.__name__} ({self._target_dir})"

    def connect(self):
        if not self._target_dir:
            raise ValueError("no target directory given!")

        if self._target_dir.exists() and not self._target_dir.is_dir():
            raise ValueError(f"target_dir {self._target_dir} exists but is not a directory. The target needs to be a directory.")

        if not self._target_dir.exists():
            logger.info(f"target dir {self._target_dir} not existing, creating")
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
            stat_local = local_path.stat()
            stat_remote = self._target_dir.joinpath(remote_path).stat()

        except Exception:
            return False
        else:
            # compare modified time (int) and size which should work on all platforms to detect equality
            return stat_local.st_size == stat_remote.st_size and int(stat_local.st_mtime) == int(stat_remote.st_mtime)

    def do_upload(self, local_path: Path, remote_path: Path):
        assert self._target_dir

        remote_path_joined_target = self._target_dir.joinpath(remote_path)
        remote_path_parent_folder_joined_target = remote_path_joined_target.parent

        if not remote_path_parent_folder_joined_target.is_dir():
            logger.info(f"creating target (sub)dir {remote_path_parent_folder_joined_target} before copying file")
            remote_path_parent_folder_joined_target.mkdir(parents=True, exist_ok=True)

        shutil.copy2(local_path, remote_path_joined_target)

    def do_delete_remote(self, remote_path: Path):
        assert self._target_dir

        self._target_dir.joinpath(remote_path).unlink(missing_ok=True)
