import json
import subprocess
import time
from pathlib import Path
from typing import Any

import niquests as requests

from .dto import AsyncJobResponse, ConfigListremotes, CoreStats, CoreVersion, JobList, JobStatus, LsJsonEntry, PubliclinkResponse
from .exceptions import RcloneConnectionException, RcloneProcessException
from .loader import resolve_rclone


class RcloneClient:
    def __init__(
        self,
        bind="localhost:5572",
        log_level: str = "NOTICE",
        transfers: int = 4,
        checkers: int = 4,
        enable_webui: bool = False,
        bwlimit: str | None = None,
    ):
        self.__bind_addr = bind
        self.__log_level = log_level
        self.__transfers = transfers
        self.__checkers = checkers
        self.__enable_webui = enable_webui
        self.__bwlimit = bwlimit
        self.__connect_addr = f"http://{bind}"
        self.__process = None
        self.__rclone_bin: Path | None = None

    # -------------------------
    # Lifecycle
    # -------------------------
    def start(self):
        if self.__process:
            return

        try:
            if not self.__rclone_bin:
                self.__rclone_bin = resolve_rclone()
        except Exception as exc:
            raise RuntimeError("rclone is not installed on this system or not on PATH. Please install it from here: https://rclone.org/") from exc

        self.__process = subprocess.Popen(
            [
                str(self.__rclone_bin),
                "rcd",
                # web-gui is always on, as the api is accessible anyways so there is no reason to disable gui "for security"
                f"--rc-addr={self.__bind_addr}",
                "--rc-no-auth",
                *(["--rc-web-gui"] if self.__enable_webui else []),
                "--rc-web-gui-no-open-browser",
                # The server needs to accept at least transfers+checkers connections, otherwise sync might fail!
                # The connections could be limited, but it could cause deadlocks, so it's preferred to change transfers/checkers only
                f"--transfers={self.__transfers}",
                f"--checkers={self.__checkers}",
                "--log-file=log/rclone.log",
                f"--log-level={self.__log_level}",
                *([f"--bwlimit={self.__bwlimit}"] if self.__bwlimit else []),
            ]
        )
        # during dev you might want to start on cli separately:
        # rclone rcd --rc-no-auth --rc-addr=localhost:5572 --rc-web-gui --transfers=4 --checkers=4 --bwlimit=5K

    def stop(self):
        if self.__process:
            self.__process.terminate()
            self.__process.wait(timeout=5)

            self.__process = None

    # -------------------------
    # Internal helper
    # -------------------------
    @staticmethod
    def is_installed() -> bool:
        try:
            resolve_rclone()
            return True
        except Exception:
            return False

    @staticmethod
    def _valid_fs_remote(fs: str, remote: str):
        # Remote backend: fs ends with ":" → dst_remote must NOT start with "/"
        assert not (fs.endswith(":") and remote.startswith("/")), f"remote must be relative when fs is a remote: {fs=} {remote=}"

        # Local backend: dst_fs does NOT end with ":" → dst_remote must start with "/"
        assert not (not fs.endswith(":") and not fs.startswith("/")), f"fs must be absolute when fs is a local path: {fs=} {remote=}"

    def _post(self, endpoint: str, data: dict[str, Any] | None = None):
        try:
            resp = requests.post(
                f"{self.__connect_addr}/{endpoint}",
                data=json.dumps(data or {}),
                headers={"Content-Type": "application/json"},
                # add header to ensure compat with rclone 1.60 (debian apt).
                # It fails using content type "application/json;charset=utf-8" which is niquests default
                # could revert to json=data in future when more recent rclone is used
                timeout=(20, 20),  # note: ConnectTimeout, ReadTimeout
                retries=0,
            )

        except requests.exceptions.RequestException as exc:
            # rclone daemon not running / wrong port / refused connection / timeout, ...
            raise RcloneConnectionException(f"Issue connecting to rclone RC server, error: {exc}") from exc

        response_json = resp.json()

        if not resp.ok:
            raise RcloneProcessException.from_dict(response_json)

        return response_json

    def _noopauth(self, input: dict):
        return self._post("rc/noopauth", input)

    def wait_for_jobs(self, job_ids: list[int]):
        _job_ids = set(job_ids)

        while self.__process:  # only wait if there is a process running
            running = set(self.job_list().runningIds)
            if _job_ids.isdisjoint(running):
                return

            time.sleep(0.05)

    # -------------------------
    # Operations
    # -------------------------

    def deletefile(self, fs: str, remote: str) -> None:
        self._valid_fs_remote(fs, remote)
        self._post("operations/deletefile", {"fs": fs, "remote": remote})

    def copyfile(self, src_fs: str, src_remote: str, dst_fs: str, dst_remote: str) -> None:
        self._valid_fs_remote(src_fs, src_remote)
        self._valid_fs_remote(dst_fs, dst_remote)
        self._post("operations/copyfile", {"srcFs": src_fs, "srcRemote": src_remote, "dstFs": dst_fs, "dstRemote": dst_remote})

    def copyfile_async(self, src_fs: str, src_remote: str, dst_fs: str, dst_remote: str) -> AsyncJobResponse:
        self._valid_fs_remote(src_fs, src_remote)
        self._valid_fs_remote(dst_fs, dst_remote)
        result = self._post(
            "operations/copyfile", {"_async": True, "srcFs": src_fs, "srcRemote": src_remote, "dstFs": dst_fs, "dstRemote": dst_remote}
        )
        return AsyncJobResponse.from_dict(result)

    def copy(self, src_fs: str, dst_fs: str, create_empty_src_dirs: bool = False) -> None:
        self._post("sync/copy", {"srcFs": src_fs, "dstFs": dst_fs, "createEmptySrcDirs": create_empty_src_dirs})

    def copy_async(self, src_fs: str, dst_fs: str, create_empty_src_dirs: bool = False) -> AsyncJobResponse:
        result = self._post("sync/copy", {"_async": True, "srcFs": src_fs, "dstFs": dst_fs, "createEmptySrcDirs": create_empty_src_dirs})
        return AsyncJobResponse.from_dict(result)

    def sync(self, src_fs: str, dst_fs: str, create_empty_src_dirs: bool = False) -> None:
        self._post("sync/sync", {"srcFs": src_fs, "dstFs": dst_fs, "createEmptySrcDirs": create_empty_src_dirs})

    def sync_async(self, src_fs: str, dst_fs: str, create_empty_src_dirs: bool = False) -> AsyncJobResponse:
        result = self._post("sync/sync", {"_async": True, "srcFs": src_fs, "dstFs": dst_fs, "createEmptySrcDirs": create_empty_src_dirs})
        return AsyncJobResponse.from_dict(result)

    def publiclink(self, fs: str, remote: str, unlink: bool = False, expire: str | None = None) -> PubliclinkResponse:
        self._valid_fs_remote(fs, remote)
        result = self._post("operations/publiclink", {"fs": fs, "remote": remote, "unlink": unlink, **({"expire": expire} if expire else {})})
        return PubliclinkResponse.from_dict(result)

    def ls(self, fs: str, remote: str) -> list[LsJsonEntry]:
        self._valid_fs_remote(fs, remote)
        response: dict = self._post("operations/list", {"fs": fs, "remote": remote})
        ls: list[dict] = response["list"]
        return [LsJsonEntry.from_dict(x) for x in ls]

    # -------------------------
    # Utilities
    # -------------------------
    def job_status(self, jobid: int) -> JobStatus:
        return JobStatus.from_dict(self._post("job/status", {"jobid": jobid}))

    def job_list(self) -> JobList:
        return JobList.from_dict(self._post("job/list"))

    # def abort_job(self, jobid: int) -> None:
    #     self._post("job/stop", {"jobid": jobid})

    # def abort_jobgroup(self, group: str) -> None:
    #     self._post("job/stopgroup", {"group": group})

    def core_stats(self) -> CoreStats:
        return CoreStats.from_dict(self._post("core/stats"))

    def version(self) -> CoreVersion:
        return CoreVersion.from_dict(self._post("core/version"))

    def config_create(self, name: str, type: str, parameters: dict[str, Any]) -> None:
        return self._post("config/create", {"name": name, "type": type, "parameters": parameters})

    def config_delete(self, name: str) -> None:
        return self._post("config/delete", {"name": name})

    def config_listremotes(self) -> ConfigListremotes:
        return ConfigListremotes.from_dict(self._post("config/listremotes"))

    def operational(self) -> bool:
        chk_input = {"op": True}
        try:
            return self._noopauth(chk_input) == chk_input
        except Exception:
            return False
