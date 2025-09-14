import logging
import threading
import time
from ftplib import FTP_TLS, error_perm, error_reply
from pathlib import Path

from ....utils.stoppablethread import StoppableThread
from ..config import FtpConnectorConfig
from .abstractconnector import AbstractConnector

logger = logging.getLogger(__name__)


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
        return f"FTP: {self._host}"

    def _monitor_idle_fun(self):
        assert self._idle_monitor_thread

        while not self._idle_monitor_thread.stopped():
            time.sleep(1)

            with self._lock:
                if self._ftp and self._idle_monitor_last_used != 0 and (time.monotonic() - self._idle_monitor_last_used) > self._idle_timeout:
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
        self._ftp = FTP_TLS(timeout=6)

        ret.append(self._ftp.connect(self._host, self._port))

        if self._secure:
            ret.append(self._ftp.auth())
            ret.append(self._ftp.login(self._username, self._password))
            ret.append(self._ftp.prot_p())
        else:
            # we still use FTP_TLS as client, so to use non-ssl/tls set secure=False and we don't need to distinguish between them
            ret.append(self._ftp.login(self._username, self._password, secure=False))

        ret.append(self._ftp.cwd("/"))

        # set binary mode for file transfers, also needed for SIZE command to work properly
        ret.append(self._ftp.voidcmd("TYPE I"))

        logger.info("FTP-Server Msg: " + "; ".join(ret))

        if not self._supports_size():
            raise RuntimeError("Your FTP server does not support SIZE command and does not work with this app.")

    def _disconnect(self):
        if self._ftp:
            try:
                ret = self._ftp.quit()
                self._ftp = None
                logger.debug("FTP-Server Msg: " + ret)
            except Exception as exc:
                # error during disconnecting is not reraised because that means probably we are disconnected...
                logger.error(f"error disconnecting: {exc}")

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

    def _supports_size(self) -> bool:
        assert self._ftp

        try:
            response = self._ftp.sendcmd("FEAT")
            return "SIZE" in response.upper()
        except Exception:
            return False

    def _get_remote_filesize(self, filepath: Path) -> int | None:
        assert self._ftp

        try:
            # check file size, if file exists returns int(bytes), if not exists, it returns None;
            # if another error occurs, it might raise an exception and we return None (so to force re-upload)
            self._ftp.cwd("/")
            size = self._ftp.size(filepath.as_posix())
        except Exception:
            size = None

        return size

    def _issame(self, local_path: Path, remote_path: Path) -> bool:
        assert self._ftp

        try:
            size_local = local_path.stat().st_size
            size_remote = self._get_remote_filesize(remote_path)
        except Exception:
            return False
        else:
            # compare size which should work on all platforms to detect equality
            return size_local == size_remote

    def _upload(self, local_path: Path, remote_path: Path):
        assert self._ftp

        try:
            self._ftp.cwd("/" + remote_path.parent.as_posix())
        except error_perm:
            # 550 → directory doesn’t exist (or no access)
            logger.debug(f"creating remote folder: {remote_path.parent}")
            self._ftp.mkd("/" + remote_path.parent.as_posix())

            self._ftp.cwd("/" + remote_path.parent.as_posix())

        try:
            with open(local_path, "rb") as f:
                self._ftp.storbinary(f"STOR {remote_path.name}", f)
        except (TimeoutError, error_reply) as err:
            logger.warning(f"error uploading the file, closing connection to start over. Error {err}")

            # close without quit to ensure for the next command the connection will be reestablished
            self._ftp.close()

            raise

    def _delete(self, remote_path: Path):
        assert self._ftp

        self._ftp.cwd("/")
        self._ftp.delete(remote_path.as_posix())

    def do_check_issame(self, local_path: Path, remote_path: Path) -> bool:
        with self._lock:
            self._ensure_connected()

            return self._issame(local_path, remote_path)

    def do_upload(self, local_path: Path, remote_path: Path):
        with self._lock:
            self._ensure_connected()

            self._upload(local_path, remote_path)

    def do_update(self, local_path: Path, remote_path: Path):
        with self._lock:
            self._ensure_connected()

            if not self._issame(local_path, remote_path):  # false if not same OR not exists
                self._upload(local_path, remote_path)

    def do_delete_remote(self, remote_path: Path):
        with self._lock:
            self._ensure_connected()

            self._delete(remote_path)
