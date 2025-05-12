import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from ftplib import FTP_TLS, all_errors, error_perm
from functools import lru_cache
from itertools import count
from pathlib import Path
from queue import Empty, PriorityQueue
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from ...utils.resilientservice import ResilientService
from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import FtpServer, ShareFtpConfig

logger = logging.getLogger(__name__)
lock = threading.Lock()
counter = count()  # tie-breaker, always incr on put to queue so the following dataclass is not compared


@dataclass
class SyncTaskUpload:
    filepath_local: Path
    filepath_remote: Path


@dataclass
class SyncTaskDelete:
    filepath_remote: Path


priorityQueueSyncType = PriorityQueue[tuple[int, int, SyncTaskUpload | SyncTaskDelete | None]]


@lru_cache(maxsize=16)
def get_folder_list_cached(_ftp: FTP_TLS, folder: Path) -> dict[str, dict[str, str]]:
    # print(folder)
    # out = {x[0]: int(x[1].get("size", 0)) for x in _ftp.mlsd(str(folder), ["size","type"])}
    try:
        out = {entry[0]: entry[1] for entry in _ftp.mlsd(str(folder), ["size", "type"])}
    except error_perm as exc:
        raise RuntimeError(f"FTP server does not support listing directory content, error: {exc}") from exc

    return out


def get_remote_filepath(local_root_dir: Path, local_filepath: Path) -> Path:
    try:
        remote_path = local_filepath.relative_to(local_root_dir)
    except ValueError as exc:
        raise ValueError(f"file {local_filepath} needs to be below root dir {local_root_dir}.") from exc

    logger.info(f"{local_filepath} maps to {remote_path}")

    return remote_path


class BaseProtocolClient(ABC):
    pass

    @abstractmethod
    def connect(self): ...
    @abstractmethod
    def disconnect(self): ...

    @abstractmethod
    def get_remote_filesize(self, filepath: Path) -> int | None: ...

    @abstractmethod
    def do_upload(self, local_path: Path, remote_path: Path): ...
    @abstractmethod
    def do_delete_remote(self, remote_path: Path): ...


class FtpProtocolClient(BaseProtocolClient):
    def __init__(self, config: FtpServer):
        super().__init__()

        self._root_dir: str = config.root_dir
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

        ret.append(self._ftp.cwd(self._root_dir))

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


class SyncWorker(ResilientService):
    def __init__(self, sync_backend, queue: priorityQueueSyncType):
        super().__init__()

        self._sync_backend: BaseProtocolClient = sync_backend  # FTPClient, ... derived from BaseClient.
        self._queue: priorityQueueSyncType = queue

        self._idle_since_seconds: int = 0
        self._idle_mode: bool = False

    def start(self):
        super().start()

    def stop(self):
        super().stop()

    def setup_resource(self):
        self._sync_backend.connect()

    def teardown_resource(self):
        self._sync_backend.disconnect()

    def run_service(self):
        assert self._sync_backend
        assert self._queue
        queue_timeout = 1  # wait until timout for a queue entry to process.
        idle_mode_timeout = 30  # after timeout disconnect and be in idle mode.

        while not self._stop_event.is_set():
            # queue_size = self._queue.qsize()
            # if queue_size > 0:
            #     print(f"noch {queue_size} zu verarbeiten.")

            try:
                priotask = self._queue.get(timeout=queue_timeout)
            except Empty:
                if not self._idle_mode:
                    self._idle_since_seconds += queue_timeout
                    if self._idle_since_seconds >= idle_mode_timeout:
                        logger.debug(f"No files to sync since {idle_mode_timeout}, disconnecting from server, waiting in idle mode")
                        self._idle_mode = True
                        self._sync_backend.disconnect()

                continue
            else:
                self._idle_since_seconds = 0
                task = priotask[2]

                # quit on shutdown.
                if task is None:
                    break

                if self._idle_mode:
                    logger.debug("Resume from idle mode, connecting to server")
                    self._sync_backend.connect()
                    self._idle_mode = False

                self._run_task(task)

    def _run_task(self, task: SyncTaskUpload | SyncTaskDelete):
        if isinstance(task, SyncTaskUpload):
            self._sync_backend.do_upload(task.filepath_local, task.filepath_remote)
        elif isinstance(task, SyncTaskDelete):
            self._sync_backend.do_delete_remote(task.filepath_remote)
        # else:
        #     raise RuntimeError()
        # TODO: what if task failed? reinsert to sync queue?

        logger.info(f"sync job finished: {task}")


# class RegularCompleteSync(ResilientService):
#     def __init__(self, sync_backend, queue, local_root_dir: Path):
#         super().__init__()

#         self._sync_backend: BaseProtocolClient = sync_backend  # FTPClient, ... derived from BaseClient.
#         self._queue: priorityQueueSyncType = queue
#         self._local_root_dir: Path = local_root_dir

#         # start resilient service activates below functions
#         self.start()

#     def start(self):
#         super().start()

#     def stop(self):
#         super().stop()

#     def setup_resource(self):
#         self._sync_backend.connect()

#     def teardown_resource(self):
#         self._sync_backend.disconnect()

#     def run_service(self):
#         assert self._sync_backend
#         assert self._queue

#         while not self._stop_event.is_set():
#             print("Starte Initial-datei sync...")

#             for local_path in Path(self._local_root_dir).glob("**/*.*"):
#                 # if self._stop_event.is_set():
#                 #     print("stop queueuing because shutdown already requested.")
#                 #     return

#                 try:
#                     remote_path = get_remote_filepath(self._local_root_dir, local_path)
#                     size = self._sync_backend.get_remote_filesize(remote_path)
#                     local_size = os.path.getsize(local_path)

#                     if size != local_size:
#                         self._queue.put_nowait((50, next(counter), SyncTaskUpload(local_path, remote_path)))
#                         print(f"queueud for upload: {local_path}")

#                 except Exception as e:
#                     print(f"Fehler bei verarbeitung von {local_path}: {e}")
#                     raise e

#             print(get_folder_list_cached.cache_info())

#             print("Initial-Synchronisation abgeschlossen.")

#             # self.stop()
#             # TODO: stop from within thread is not allowed (deadlock!) need to figure out a way to have a one-time living service.


class ShareFtp(BasePlugin[ShareFtpConfig]):
    def __init__(self):
        super().__init__()

        self._config: ShareFtpConfig = ShareFtpConfig()
        self._local_root_dir: Path = Path("./media/")

        self._queue: priorityQueueSyncType = PriorityQueue()

        self._sync_worker = None

    def get_new_client(self):
        # could instanciate different clients in future here...
        return FtpProtocolClient(self._config.ftp_server)

    @hookimpl
    def start(self):
        """To start the resilient service"""

        if not self._config.common.enabled:
            logger.info("Share FTP is disabled")
            return

        # start with fresh queue
        self._queue: priorityQueueSyncType = PriorityQueue()

        # consumes the queue and uploads/deletes/modifies remote filesystem according to the queue.
        sync_client = self.get_new_client()
        self._sync_worker = SyncWorker(sync_client, self._queue)
        self._sync_worker.start()

    @hookimpl
    def stop(self):
        """To stop the resilient service"""

        self._queue.put_nowait((0, next(counter), None))  # lowest (==highest) priority for None to stop processing.

        if self._sync_worker:
            self._sync_worker.stop()

    @hookimpl
    def get_share_link(self, identifier: UUID, filename: str):
        logger.info(f"GETTING SHARE LINK {identifier} {filename}")

        download_portal_url = f"{self._config.common.share_url.rstrip('/')}/#/?url="

        mediaitem_url = self._config.common.media_url
        mediaitem_url = mediaitem_url.replace("{filename}", filename)
        mediaitem_url = mediaitem_url.replace("{identifier}", str(identifier))

        return download_portal_url + quote(mediaitem_url, safe="")

    @hookimpl
    def collection_original_file_added(self, files: list[Path]):
        logger.info(f"SYNC File ORIGINAL ADDED NOTE {files}")
        for file in files:
            self._queue.put_nowait((20, next(counter), SyncTaskUpload(file, get_remote_filepath(self._local_root_dir, file))))

    @hookimpl
    def collection_files_added(self, files: list[Path]):
        logger.info(f"SYNC File added NOTE {files}")
        for file in files:
            self._queue.put_nowait((10, next(counter), SyncTaskUpload(file, get_remote_filepath(self._local_root_dir, file))))

    @hookimpl
    def collection_files_updated(self, files: list[Path]):
        logger.info(f"SYNC File updated NOTE {files}")
        for file in files:
            self._queue.put_nowait((10, next(counter), SyncTaskUpload(file, get_remote_filepath(self._local_root_dir, file))))

    @hookimpl
    def collection_files_deleted(self, files: list[Path]):
        logger.info(f"SYNC File delete NOTE {files}")
        for file in files:
            self._queue.put_nowait((15, next(counter), SyncTaskDelete(get_remote_filepath(self._local_root_dir, file))))
