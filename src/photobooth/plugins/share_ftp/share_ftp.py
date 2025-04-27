import logging
import os
import threading
from dataclasses import dataclass
from ftplib import FTP_TLS, error_perm
from functools import lru_cache
from pathlib import Path
from queue import Empty, Queue
from typing import Literal

from ...utils.resilientservice import ResilientService
from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import ShareFtpConfig

logger = logging.getLogger(__name__)


@dataclass
class FtpTask:
    cmd: Literal["upload", "delete"]
    file: Path


class ShareFtp(ResilientService, BasePlugin[ShareFtpConfig]):
    def __init__(self):
        super().__init__()

        self._config: ShareFtpConfig = ShareFtpConfig()
        self._local_dir: Path = Path("./media/")

        self._ftp: FTP_TLS | None = None

        self._service_ready: threading.Event = threading.Event()

        # None in queue can be used on shutdown to reduce waiting for timeout
        self._queue: Queue[FtpTask | None] = Queue()

    @hookimpl
    def start(self):
        """To start the resilient service"""

        if not self._config.shareftp_enabled:
            logger.info("Share FTP is disabled")
            return

        super().start()

    @hookimpl
    def stop(self):
        """To stop the resilient service"""

        super().stop()

    def setup_resource(self):
        # reset queue on start to avoid any leftovers...
        self._queue = Queue()

        # FTP_TLS-Verbindung aufbauen
        self._ftp = FTP_TLS(self._config.ftp_host, timeout=5)
        self._ftp.login(self._config.ftp_username, self._config.ftp_password)
        self._ftp.prot_p()

        self._ftp.cwd(self._config.ftp_remote_dir)

    def teardown_resource(self):
        self._service_ready.clear()

        # clear queue on shutdown so None has immediate shutdown effect.
        try:
            while True:
                self._queue.get_nowait()
        except Empty:
            pass

        self._queue.put(None)

        if self._ftp:
            self._ftp.quit()

    def wait_until_ready(self, timeout: float = 5) -> bool:
        return self._service_ready.wait(timeout=timeout)

    @hookimpl
    def collection_files_added(self, files: list[Path]):
        logger.info(f"SYNC File added NOTE {files}")
        for file in files:
            self._queue.put(FtpTask("upload", file))

    @hookimpl
    def collection_files_updated(self, files: list[Path]):
        logger.info(f"SYNC File updated NOTE {files}")
        for file in files:
            self._queue.put(FtpTask("upload", file))

    @hookimpl
    def collection_files_deleted(self, files: list[Path]):
        logger.info(f"SYNC File delete NOTE {files}")
        for file in files:
            self._queue.put(FtpTask("delete", file))

    @lru_cache(maxsize=16)
    def get_folder_files_sizes(self, folder: Path) -> dict[str, int]:
        assert self._ftp
        out = {x[0]: int(x[1].get("size", 0)) for x in self._ftp.mlsd(str(folder), ["size"])}

        return out

    def get_remote_filesize(self, filepath: Path) -> int | None:
        assert self._ftp

        sizes = self.get_folder_files_sizes(filepath.parent)

        # if file is not found in the list, return None which means the file probably needs to be uploaded.
        size = sizes.get(filepath.name, None)

        return size

    def run_service(self):
        assert self._ftp

        # Initial Sync durchführen
        self._initial_sync_folderstructure()
        self._initial_delta_queue()

        self._service_ready.set()

        while not self._stop_event.is_set():
            queue_size = self._queue.qsize()
            if queue_size > 0:
                print(f"noch {queue_size} zu verarbeiten.")

            try:
                task = self._queue.get(timeout=1)
            except Empty:
                continue
            else:
                # quit on shutdown.
                if task is None:
                    break

                self._run_ftp_task(task)

    def _run_ftp_task(self, task: FtpTask):
        assert self._ftp
        if task.cmd == "upload":
            self._ftp_upload(task.file)
        elif task.cmd == "delete":
            self._ftp_remote_delete_file(task.file)
        # else not possible because of literal.

        print(f"task done: {task}")

    def _ftp_upload(self, local_path: Path):
        assert self._ftp

        remote_path = self._get_remote_filepath(local_path)

        with open(local_path, "rb") as f:
            self._ftp.storbinary(f"STOR {remote_path}", f)

        print(f"hochgeladen: {remote_path}")

    def _ftp_remote_delete_file(self, local_path: Path):
        assert self._ftp
        remote_path = self._get_remote_filepath(local_path)

        self._ftp.delete(str(remote_path))

        print(f"gelöscht: {remote_path}")

    def _get_remote_filepath(self, local_filepath: Path) -> Path:
        remote_path = Path(self._config.ftp_remote_dir, local_filepath.relative_to(self._local_dir))
        # print(f"{local_filepath} maps to {remote_path}")

        return remote_path

    def _initial_sync_folderstructure(self):
        assert self._ftp

        print("Starte Initial-ordnerstruktur-sync...")
        for local_path in Path(self._local_dir).glob("**/*"):
            if not local_path.is_dir():
                continue

            try:
                remote_path = self._get_remote_filepath(local_path)
                self._ftp.mkd(str(remote_path))
                print(f"Verzeichnis erstellt: {remote_path}")
            except error_perm:
                pass  # Existiert bereits
                # ? was mit anderen fehlern?

    def _initial_delta_queue(self):
        assert self._ftp

        print("Starte Initial-datei sync...")

        for local_path in Path(self._local_dir).glob("**/*.*"):
            if self._stop_event.is_set():
                print("stop queueuing because shutdown already requested.")
                return

            try:
                size = self.get_remote_filesize(self._get_remote_filepath(local_path))
                local_size = os.path.getsize(local_path)

                if size != local_size:
                    self._queue.put(FtpTask("upload", local_path))
                    print(f"queueud for upload: {local_path}")

            except Exception as e:
                print(f"Fehler bei verarbeitung von {local_path}: {e}")
                raise e

        print(self.get_folder_files_sizes.cache_info())

        print("Initial-Synchronisation abgeschlossen.")
