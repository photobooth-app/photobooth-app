import logging
from pathlib import Path

import nc_py_api

from ..config import NextcloudBackendConfig
from .base import BaseBackend

logger = logging.getLogger(__name__)

class NextcloudBackend(BaseBackend):
    def __init__(self, config: NextcloudBackendConfig):
        super().__init__()

        self._url: str = config.url
        self._username: str = config.username
        self._password: str = config.password.get_secret_value()

        self._target_dir: Path = Path(config.target_dir)

    def connect(self):
        ret = []

        if not self._url:
            raise ValueError("no host given!")

        # create Nextcloud client instance class
        self.nc = nc_py_api.Nextcloud(nextcloud_url=self._url, nc_auth_user=self._username, nc_auth_pass=self._password)

        logger.info("Nextcloud: " + str(self.nc.srv_version))

    def disconnect(self):
        raise NotImplementedError

    def get_remote_samefile(self, local_path: Path, remote_path: Path) -> bool:
        raise NotImplementedError

    def do_upload(self, local_path: Path, remote_path: Path):
        full_path = self._target_dir.joinpath(remote_path)
        # Ensure directory exists
        self.nc.files.makedirs(str(full_path.parent), True)
        # Do upload
        res = self.nc.files.upload_stream(str(full_path), local_path)
        logger.info("Uploaded: " + res.full_path)


    def do_delete_remote(self, remote_path: Path):
        full_path = self._target_dir.joinpath(remote_path)
        self.nc.files.delete(str(full_path))
        logger.info("Deleted: " + str(full_path))
