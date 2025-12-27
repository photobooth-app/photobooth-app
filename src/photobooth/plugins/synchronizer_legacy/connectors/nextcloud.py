import logging
from pathlib import Path

from nc_py_api import Nextcloud

from ..config import NextcloudConnectorConfig
from .abstractconnector import AbstractConnector

logger = logging.getLogger(__name__)


class NextcloudConnector(AbstractConnector):
    def __init__(self, config: NextcloudConnectorConfig):
        super().__init__(config)

        self._url: str = str(config.url)
        self._username: str = config.username
        self._password: str = config.password.get_secret_value()

        self._target_dir: Path = Path(config.target_dir)

        self.nc: Nextcloud | None = None

    def __str__(self):
        return f"NextCloud: {self._url.rstrip('/')}/{self._target_dir}"

    def connect(self):
        if not self._url:
            raise ValueError("no host given!")

        # create Nextcloud client instance class
        self.nc = Nextcloud(nextcloud_url=self._url, nc_auth_user=self._username, nc_auth_pass=self._password)

        logger.info(f"Nextcloud server connected: v{self.nc.srv_version}")

    def disconnect(self):
        # Nexcloud client seems to be stateless(?), so no disconnect needed.
        pass

    def is_connected(self) -> bool:
        if not self.nc:
            return False

        try:
            self.nc.update_server_info()
            # self.nc.user_status.get_current()
        except Exception:
            return False
        else:
            return True

    def do_check_issame(self, local_path: Path, remote_path: Path) -> bool:
        assert self.nc

        try:
            local_size = local_path.stat().st_size
            remote_size = self.nc.files.by_path(self._target_dir.joinpath(remote_path).as_posix()).info.size  # type: ignore
        except Exception:
            return False
        else:
            # compare size which should work on all platforms to detect equality
            return local_size == remote_size

    def do_upload(self, local_path: Path, remote_path: Path):
        assert self.nc

        full_path = self._target_dir.joinpath(remote_path)
        # Ensure directory exists
        self.nc.files.makedirs(full_path.parent.as_posix(), True)

        # Do upload
        self.nc.files.upload_stream(full_path.as_posix(), local_path)

    def do_update(self, local_path: Path, remote_path: Path):
        if not self.do_check_issame(local_path, remote_path):  # false if not same OR not exists
            self.do_upload(local_path, remote_path)

    def do_delete_remote(self, remote_path: Path):
        assert self.nc

        full_path = self._target_dir.joinpath(remote_path)

        self.nc.files.delete(full_path.as_posix())
