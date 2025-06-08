import logging
import threading
from ftplib import FTP_TLS
from functools import lru_cache
from pathlib import Path
from typing import Literal

from ..config import FtpConnectorConfig
from .base import BaseConnector, BaseMediashare

logger = logging.getLogger(__name__)


@lru_cache(maxsize=16)
def get_folder_list_cached(_ftp: FTP_TLS, folder: Path) -> dict[str, dict[str, str]]:
    # print(folder)
    # out = {x[0]: int(x[1].get("size", 0)) for x in _ftp.mlsd(str(folder), ["size","type"])}
    out = {entry[0]: entry[1] for entry in _ftp.mlsd(str(folder), ["size", "type"])}

    return out


class FtpConnector(BaseConnector):
    def __init__(self, config: FtpConnectorConfig):
        super().__init__()

        self._host: str = config.host
        self._port: int = config.port
        self._username: str = config.username
        self._password: str = config.password.get_secret_value()
        self._secure: bool = config.secure

        self._ftp: FTP_TLS | None = None
        self._lock = threading.Lock()

    def connect(self):
        ret = []

        if not self._host:
            raise ValueError("no host given!")

        # FTP_TLS-Verbindung aufbauen
        self._ftp = FTP_TLS(timeout=5)

        ret.append(self._ftp.connect(self._host, self._port))

        if self._secure:
            ret.append(self._ftp.auth())
            ret.append(self._ftp.login(self._username, self._password))
            ret.append(self._ftp.prot_p())
        else:
            # we still use FTP_TLS as client, so to use non-ssl/tls set secure=False and we don't need to distinguish between them
            ret.append(self._ftp.login(self._username, self._password, secure=False))

        ret.append(self._ftp.cwd("/"))

        logger.info("FTP-Server Msg: " + "; ".join(ret))

    def disconnect(self):
        if self._ftp:
            try:
                ret = self._ftp.quit()
                self._ftp = None
                logger.debug("FTP-Server Msg: " + ret)
            except Exception as exc:
                # error during disconnecting is not reraised because that means probably we are disconnected...
                logger.error(f"error disconnting: {exc}")

    def is_connected(self) -> bool:
        if not self._ftp:
            return False

        try:
            # Send a NOOP command to check connection
            self._ftp.voidcmd("NOOP")
            return True
        except Exception as e:
            logger.debug(f"FTP connection check failed: {e}")
            return False

    def ensure_connected(self):
        if not self.is_connected():
            self.connect()

    def get_folder_list(self, remote_path: Path):
        with self._lock:
            self.ensure_connected()

            folder_list = get_folder_list_cached(self._ftp, remote_path)

        return folder_list

    def get_remote_istype(self, filepath: Path, type: Literal["dir", "cdir", "pdir", "file"]) -> bool:
        assert self._ftp

        folder_list = self.get_folder_list(filepath.parent)

        # if file is not found in the list, return None which means the file probably needs to be uploaded.
        try:
            ftype = folder_list[filepath.name]["type"]  # raise KeyError if name not in list
        except Exception:
            ftype = None

        return ftype == type

    def get_remote_filesize(self, filepath: Path) -> int | None:
        assert self._ftp

        folder_list = self.get_folder_list(filepath.parent)

        # if file is not found in the list,NextcloudBackend return None which means the file probably needs to be uploaded.
        try:
            size = int(folder_list[filepath.name]["size"])  # raise KeyError if name/type not in list
        except Exception:
            size = None

        return size

    def get_remote_samefile(self, local_path: Path, remote_path: Path) -> bool:
        assert self._ftp

        try:
            size_local = local_path.stat().st_size
            size_remote = self.get_remote_filesize(remote_path)
        except Exception:
            return False
        else:
            # compare size which should work on all platforms to detect equality
            return size_local == size_remote

    def do_upload(self, local_path: Path, remote_path: Path):
        assert self._ftp

        with self._lock:
            self.ensure_connected()

            if not self.get_remote_istype(remote_path.parent, "dir"):
                logger.debug(f"creating remote folder: {remote_path}")
                self._ftp.mkd(str(remote_path.parent))

            get_folder_list_cached.cache_clear()

            with open(local_path, "rb") as f:
                self._ftp.storbinary(f"STOR {remote_path}", f)

            logger.info(f"Uploaded {local_path} to remote {remote_path}")

    def do_delete_remote(self, remote_path: Path):
        assert self._ftp

        with self._lock:
            self.ensure_connected()

            get_folder_list_cached.cache_clear()

            self._ftp.delete(str(remote_path))


class FtpMediashare(BaseMediashare):
    def __init__(self, media_url: str):
        mediaitem_url = media_url.rstrip("/") + "{remote_path}"

        super().__init__(mediaitem_url)
