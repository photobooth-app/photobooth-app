import logging
from pathlib import Path

import nextcloud_client

from ..config import NextcloudBackendConfig
from .base import BaseBackend

logger = logging.getLogger(__name__)

class NextcloudBackend(BaseBackend):
    def __init__(self, config: NextcloudBackendConfig):
        super().__init__()

        self._url: str = config.url
        self._username: str = config.username
        self._password: str = config.password.get_secret_value()

    def connect(self):
        ret = []

        if not self._url:
            raise ValueError("no host given!")

        self.nc = nextcloud_client.Client(self._url)

        self.nc.login(self._username, self._password)

    def disconnect(self):
        raise NotImplementedError

    def get_remote_samefile(self, local_path: Path, remote_path: Path) -> bool:
        raise NotImplementedError

    def do_upload(self, local_path: Path, remote_path: Path):
        self.nc.put_file(remote_path, local_path)

    def do_delete_remote(self, remote_path: Path):
        self.nc.drop_file(str(remote_path))
