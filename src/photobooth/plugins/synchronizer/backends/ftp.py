import logging
import threading
from ftplib import FTP_TLS, all_errors, error_perm
from functools import lru_cache
from pathlib import Path
from typing import Literal

from ..config import FtpServerBackendConfig
from .base import BaseBackend

logger = logging.getLogger(__name__)
lock = threading.Lock()


@lru_cache(maxsize=16)
def get_folder_list_cached(_ftp: FTP_TLS, folder: Path) -> dict[str, dict[str, str]]:
    # print(folder)
    # out = {x[0]: int(x[1].get("size", 0)) for x in _ftp.mlsd(str(folder), ["size","type"])}
    try:
        out = {entry[0]: entry[1] for entry in _ftp.mlsd(str(folder), ["size", "type"])}
    except error_perm as exc:
        raise RuntimeError(f"FTP server does not support listing directory content, error: {exc}") from exc

    return out


class FtpBackend(BaseBackend):
    def __init__(self, config: FtpServerBackendConfig):
        super().__init__()

        self._host: str = config.host
        self._port: int = config.port
        self._username: str = config.username
        self._password: str = config.password.get_secret_value()
        self._secure: bool = config.secure

        self._ftp: FTP_TLS | None = None

        # None in queue can be used on shutdown to reduce waiting for timeout
        # self._queue: Queue[SyncTaskUpload | SyncTaskDelete | None] = Queue()

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

        # ret.append(self._ftp.cwd(self._root_dir))
        ret.append(self._ftp.cwd("/"))

        logger.info("FTP-Server Msg: " + "; ".join(ret))

    def disconnect(self):
        if self._ftp:
            try:
                ret = self._ftp.quit()
                self._ftp = None
                logger.debug("FTP-Server Msg: " + ret)
            except all_errors as exc:
                print(exc)
                print("error disconn, but we just ignore this because on disc. failing quit means its disconnected from client perspective")

    def get_folder_list(self, remote_path: Path):
        folder_list = get_folder_list_cached(self._ftp, remote_path)
        return folder_list

    def get_remote_istype(self, filepath: Path, type: Literal["dir", "cdir", "pdir", "file"]) -> bool:
        assert self._ftp

        ftype = None

        folder_list = self.get_folder_list(filepath.parent)

        # if file is not found in the list, return None which means the file probably needs to be uploaded.
        facts = folder_list.get(filepath.name, None)

        if facts:
            ftype = facts.get("type", None)

        return ftype == type

    def get_remote_samefile(self, local_path: Path, remote_path: Path) -> bool:
        raise NotImplementedError

    def get_remote_filesize(self, filepath: Path) -> int | None:
        assert self._ftp

        size = None
        out = None

        folder_list = self.get_folder_list(filepath.parent)

        # if file is not found in the list, return None which means the file probably needs to be uploaded.
        facts = folder_list.get(filepath.name, None)

        if facts:
            size = facts.get("size", None)

        if size:
            out = int(size)

        return out

    def do_upload(self, local_path: Path, remote_path: Path):
        assert self._ftp

        # print(local_path)
        # print(remote_path)

        with lock:  # two clients *could* operate on the same folder in theory.
            if not self.get_remote_istype(remote_path.parent, "dir"):
                logger.debug(f"creating remote folder: {remote_path}")
                try:
                    self._ftp.mkd(str(remote_path.parent))
                except Exception as exc:
                    logger.error(f"error creating folder {remote_path}: {exc}")
                    raise exc
                else:
                    get_folder_list_cached.cache_clear()

        with open(local_path, "rb") as f:
            self._ftp.storbinary(f"STOR {remote_path}", f)

    def do_delete_remote(self, remote_path: Path):
        assert self._ftp

        self._ftp.delete(str(remote_path))
