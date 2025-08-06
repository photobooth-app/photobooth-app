import logging
import threading
import time
from ftplib import FTP_TLS
from functools import lru_cache
from pathlib import Path
from typing import Literal

from ....utils.stoppablethread import StoppableThread
from ..config import FtpConnectorConfig
from .abstractconnector import AbstractConnector

logger = logging.getLogger(__name__)


@lru_cache(maxsize=16)
def _get_folder_list_cached(_ftp: FTP_TLS, folder: Path) -> dict[str, dict[str, str]]:
    # print(folder)
    # out = {x[0]: int(x[1].get("size", 0)) for x in _ftp.mlsd(str(folder), ["size","type"])}
    out = {entry[0]: entry[1] for entry in _ftp.mlsd(folder.as_posix(), ["size", "type"])}

    return out


class FtpConnector(AbstractConnector):
    def __init__(self, config: FtpConnectorConfig):
        super().__init__(config)

        self._host: str = config.host
        self._port: int = config.port
        self._username: str = config.username
        self._password: str = config.password.get_secret_value()
        self._secure: bool = config.secure
        self._idle_timeout: int = config.idle_timeout

        self._ftp: FTP_TLS | None = None
        self._lock = threading.Lock()

        self._idle_monitor_thread = StoppableThread(name="_ftp_monitor_idle_thread", target=self._monitor_idle_fun, daemon=True)
        self._idle_monitor_last_used: float = 0
        self._idle_monitor_thread.start()

    def __str__(self):
        return f"{self.__class__.__name__} ({self._host})"

    def _monitor_idle_fun(self):
        assert self._idle_monitor_thread

        while not self._idle_monitor_thread.stopped():
            time.sleep(1)

            with self._lock:
                if self._ftp and (time.monotonic() - self._idle_monitor_last_used) > self._idle_timeout:
                    logger.debug(f"Ftp connection idle for {self._idle_timeout}s. Disconnecting from server...")
                    try:
                        self._ftp.quit()
                    except Exception:
                        pass

                    self._ftp = None

    def connect(self):
        with self._lock:
            self._connect()

    def disconnect(self):
        with self._lock:
            self._disconnect()

        if self._idle_monitor_thread and self._idle_monitor_thread.is_alive():
            self._idle_monitor_thread.stop()
            self._idle_monitor_thread.join()

    def is_connected(self) -> bool:
        """externally usable function to check for connection - lock protected as all other externally used funcs"""
        with self._lock:
            return self._is_connected()

    def _connect(self):
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

        if not self._supports_mlsd():
            raise RuntimeError("Your FTP server does not support MLSD command and does not work with this app.")

    def _disconnect(self):
        if self._ftp:
            try:
                ret = self._ftp.quit()
                self._ftp = None
                logger.debug("FTP-Server Msg: " + ret)
            except Exception as exc:
                # error during disconnecting is not reraised because that means probably we are disconnected...
                logger.error(f"error disconnting: {exc}")

    def _is_connected(self) -> bool:
        """internally used to check connection. no lock protection, because other functions check for it"""
        if not self._ftp:
            return False

        try:
            # Send a NOOP command to check connection
            self._ftp.voidcmd("NOOP")
            return True
        except Exception as e:
            logger.debug(f"FTP connection check failed: {e}")
            return False

    def _ensure_connected(self):
        if not self._is_connected():
            self._connect()

        self._idle_monitor_last_used = time.monotonic()

    def _supports_mlsd(self) -> bool:
        """Check if the server supports MLSD (MLST support usually implies MLSD but MLSD might not be advertised)."""
        assert self._ftp

        try:
            features = self._ftp.sendcmd("FEAT").splitlines()
            return any("MLST" in feat or "MLSD" in feat for feat in features)
        except Exception:
            return False

    def _get_folder_list(self, remote_path: Path):
        assert self._ftp

        folder_list = _get_folder_list_cached(self._ftp, remote_path)

        return folder_list

    def _get_remote_istype(self, filepath: Path, rtype: tuple[Literal["dir", "cdir", "pdir", "file"], ...]) -> bool:
        assert self._ftp

        folder_list = self._get_folder_list(filepath.parent)

        # if file is not found in the list, return None which means the file probably needs to be uploaded.
        try:
            ftype = folder_list[str(filepath)]["type"]  # raise KeyError if name not in list
        except Exception:
            ftype = None

        return ftype in rtype

    def _get_remote_filesize(self, filepath: Path) -> int | None:
        assert self._ftp

        folder_list = self._get_folder_list(filepath.parent)

        # if file is not found in the list,NextcloudBackend return None which means the file probably needs to be uploaded.
        try:
            size = int(folder_list[filepath.name]["size"])  # raise KeyError if name/type not in list
        except Exception:
            size = None

        return size

    def get_remote_samefile(self, local_path: Path, remote_path: Path) -> bool:
        with self._lock:
            self._ensure_connected()
            assert self._ftp

            try:
                size_local = local_path.stat().st_size
                size_remote = self._get_remote_filesize(remote_path)
            except Exception:
                return False
            else:
                # compare size which should work on all platforms to detect equality
                return size_local == size_remote

    def do_upload(self, local_path: Path, remote_path: Path):
        with self._lock:
            self._ensure_connected()
            assert self._ftp

            if not self._get_remote_istype(remote_path.parent, ("dir", "cdir")):
                logger.debug(f"creating remote folder: {remote_path.parent}")
                self._ftp.mkd(remote_path.parent.as_posix())

            _get_folder_list_cached.cache_clear()

            with open(local_path, "rb") as f:
                self._ftp.storbinary(f"STOR {remote_path.as_posix()}", f)

    def do_delete_remote(self, remote_path: Path):
        with self._lock:
            self._ensure_connected()
            assert self._ftp

            _get_folder_list_cached.cache_clear()

            self._ftp.delete(remote_path.as_posix())
