import subprocess
from dataclasses import dataclass
from shutil import which
from typing import Any

import niquests as requests


class RcloneConnectionException(Exception): ...


class RcloneProcessException(Exception):
    def __init__(self, error: str, input: dict | None, status: int | None, path: str | None):
        super().__init__(error)
        self.error = error
        self.input = input
        self.status = status
        self.path = path

    @staticmethod
    def from_dict(d: dict) -> "RcloneProcessException":
        return RcloneProcessException(
            error=d.get("error", "Unknown error"),
            input=d.get("input", None),
            status=d.get("status", None),
            path=d.get("path", None),
        )

    def __str__(self):
        return f"RcloneProcessException(status={self.status}, path='{self.path}', error='{self.error}', input={self.input})"


@dataclass
class CoreVersion:
    version: str

    @staticmethod
    def from_dict(d: dict[str, Any]):
        return CoreVersion(version=d.get("version", "unknown"))


@dataclass
class ConfigListremotes:
    remotes: list[str]

    @staticmethod
    def from_dict(d: dict[str, Any]):
        return ConfigListremotes(remotes=d.get("remotes", []))


@dataclass
class AsyncJobResponse:
    jobid: int | None

    @staticmethod
    def from_dict(d: dict[str, Any]):
        return AsyncJobResponse(jobid=d.get("jobid"))


@dataclass
class JobStatus:
    finished: bool
    duration: float
    end_time: str | None
    error: str | None
    id: int
    execute_id: int | None
    start_time: str | None
    success: bool
    output: Any
    progress: Any

    @staticmethod
    def from_dict(d: dict[str, Any]):
        return JobStatus(
            finished=d.get("finished", False),
            duration=d.get("duration", 0.0),
            end_time=d.get("endTime"),
            error=d.get("error"),
            id=d.get("id", 0),
            execute_id=d.get("executeId"),
            start_time=d.get("startTime"),
            success=d.get("success", False),
            output=d.get("output"),
            progress=d.get("progress"),
        )


@dataclass
class CoreStats:
    bytes: int
    speed: float
    checks: int
    deletes: int
    elapsedTime: float

    @staticmethod
    def from_dict(d: dict[str, Any]):
        return CoreStats(
            bytes=d.get("bytes", 0),
            speed=d.get("speed", 0.0),
            checks=d.get("checks", 0),
            deletes=d.get("deletes", 0),
            elapsedTime=d.get("elapsedTime", 0.0),
        )


class RcloneClient:
    def __init__(self, addr="http://localhost:5572"):
        self.addr = addr
        self.process = None
        self.current_sync_job: int | None = None

    # -------------------------
    # Lifecycle
    # -------------------------
    def start(self):
        if self.process:
            return

        if not self.is_installed():
            raise Exception("rclone is not installed on this system. Please install it from here: https://rclone.org/")

        # self.process = subprocess.Popen(["rclone", "rcd", "--rc-no-auth", "--rc-addr=localhost:5572"])
        self.process = subprocess.Popen(["rclone", "rcd", "--rc-no-auth", "--rc-addr=localhost:5572", "--rc-web-gui", "--transfers=4"])

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process = None

    # -------------------------
    # Internal helper
    # -------------------------

    @staticmethod
    def is_installed() -> bool:
        return which("rclone") is not None

    def _post(self, endpoint: str, data: dict[str, str | int | bool] | None = None):
        try:
            resp = requests.post(f"{self.addr}/{endpoint}", json=data or {})
        except requests.exceptions.RequestException as exc:
            # rclone daemon not running / wrong port / refused connection / timeout, ...
            raise RcloneConnectionException(f"Issue connecting to rclone RC server, error: {exc}") from exc

        response_json = resp.json()

        if not resp.ok:
            raise RcloneProcessException.from_dict(response_json)

        # print(response_json)
        return response_json

    def _noopauth(self, input: dict):
        return self._post("rc/noopauth", input)

    # -------------------------
    # Operations
    # -------------------------

    def copyfile(self, src_fs: str, src_remote: str, dst_fs: str, dst_remote: str) -> None:
        self._post("operations/copyfile", {"srcFs": src_fs, "srcRemote": src_remote, "dstFs": dst_fs, "dstRemote": dst_remote})

    def deletefile(self, fs: str, remote: str) -> None:
        self._post("operations/deletefile", {"fs": fs, "remote": remote})

    def sync(self, src_fs: str, dst_fs: str) -> None:
        self._post("sync/sync", {"srcFs": src_fs, "dstFs": dst_fs})

    def abort_job(self, jobid: int) -> None:
        self._post("job/stop", {"jobid": jobid})

    def abort_jobgroup(self, group: str) -> None:
        self._post("job/stopgroup", {"group": group})

    def a_copy(self, src_fs: str, src_remote: str, dst_fs: str, dst_remote: str) -> AsyncJobResponse:
        result = self._post(
            "operations/copyfile", {"_async": True, "srcFs": src_fs, "srcRemote": src_remote, "dstFs": dst_fs, "dstRemote": dst_remote}
        )
        return AsyncJobResponse.from_dict(result)

    def a_sync(self, src_fs: str, dst_fs: str) -> AsyncJobResponse:
        result = self._post("sync/sync", {"_async": True, "srcFs": src_fs, "dstFs": dst_fs})
        return AsyncJobResponse.from_dict(result)

    # -------------------------
    # Utilities
    # -------------------------
    def job_status(self, jobid: int):
        return JobStatus.from_dict(self._post("job/status", {"jobid": jobid}))

    def stats(self) -> CoreStats:
        return CoreStats.from_dict(self._post("core/stats"))

    def version(self) -> CoreVersion:
        return CoreVersion.from_dict(self._post("core/version"))

    def listremotes(self):
        return ConfigListremotes.from_dict(self._post("config/listremotes"))

    def alive(self):
        chk_input = {"alive": True}
        return self._noopauth(chk_input) == chk_input


if __name__ == "__main__":
    client = RcloneClient()

    print(client.version())
    print(client.stats())
    print(client.listremotes())
    print(client.alive())

    print(
        client.sync(
            "media",
            f"{'localremote'.rstrip(':')}:{'subdir_api'.rstrip('/')}/",
        )
    )

    print(
        client.copyfile(
            "/home/michael/dev/photobooth/photobooth-app/",  # local files seems need to be absolute?! but this is not true for sync?!
            "src/web/download/index.html",
            f"{'localremote'.rstrip(':')}:",
            f"{'subdir_api'.rstrip('/')}/index.html",
        )
    )
    try:
        print(client._post("rc/error"))
    except RcloneProcessException as exc:
        print("got error")
        print(exc)
    try:
        print(client._post("rc/fatal"))
    except RcloneProcessException as exc:
        print("got fatal err")
        print(exc.status)

    # print(client._post("rc/list"))
    print(client._post("rc/noop", {"input": "test"}))
