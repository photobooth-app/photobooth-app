import subprocess
from shutil import which
from typing import Any

import niquests as requests

from .dto import AsyncJobResponse, ConfigListremotes, CoreStats, CoreVersion, JobList, JobStatus
from .exceptions import RcloneConnectionException, RcloneProcessException


class RcloneClient:
    def __init__(self, bind="localhost:5572", log_level: str = "NOTICE", transfers: int = 4, checkers: int = 4):
        self.__bind_addr = bind
        self.__log_level = log_level
        self.__transfers = transfers
        self.__checkers = checkers
        self.__connect_addr = f"http://{bind}"
        self.__process = None

    # -------------------------
    # Lifecycle
    # -------------------------
    def start(self):
        if self.__process:
            return

        if not self.is_installed():
            raise Exception("rclone is not installed on this system or not on PATH. Please install it from here: https://rclone.org/")

        self.__process = subprocess.Popen(
            [
                "rclone",
                "rcd",
                # web-gui is always on, as the api is accessible anyways so there is no reason to disable gui "for security"
                f"--rc-addr={self.__bind_addr}",
                "--rc-no-auth",
                "--rc-web-gui",
                "--rc-web-gui-no-open-browser",
                # The server needs to accept at least transfers+checkers connections, otherwise sync might fail!
                # The connections could be limited, but it could cause deadlocks, so it's preferred to change transfers/checkers only
                f"--transfers={self.__transfers}",
                f"--checkers={self.__checkers}",
                "--log-file=log/rclone.log",
                f"--log-level={self.__log_level}",
            ]
        )
        # during dev you might want to start on cli separately:
        # rclone rcd --rc-no-auth --rc-addr=localhost:5572 --rc-web-gui --transfers=4 --checkers=4 --bwlimit=50K

    def stop(self):
        if self.__process:
            self.__process.terminate()
            self.__process = None

    # -------------------------
    # Internal helper
    # -------------------------

    @staticmethod
    def is_installed() -> bool:
        return which("rclone") is not None

    def _post(self, endpoint: str, data: dict[str, Any] | None = None):
        try:
            resp = requests.post(
                f"{self.__connect_addr}/{endpoint}",
                json=data or {},
                timeout=(20, 5, 20),  # note: TotalTimeout, ConnectTimeout, ReadTimeout
                retries=0,
            )
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

    def deletefile(self, fs: str, remote: str) -> None:
        self._post(
            "operations/deletefile",
            {"fs": fs, "remote": remote},
        )

    def copyfile(self, src_fs: str, src_remote: str, dst_fs: str, dst_remote: str) -> None:
        self._post("operations/copyfile", {"srcFs": src_fs, "srcRemote": src_remote, "dstFs": dst_fs, "dstRemote": dst_remote})

    def copyfile_async(self, src_fs: str, src_remote: str, dst_fs: str, dst_remote: str) -> AsyncJobResponse:
        result = self._post(
            "operations/copyfile",
            {"_async": True, "srcFs": src_fs, "srcRemote": src_remote, "dstFs": dst_fs, "dstRemote": dst_remote},
        )
        return AsyncJobResponse.from_dict(result)

    def copy(self, src_fs: str, dst_fs: str, create_empty_src_dirs: bool = False) -> None:
        self._post(
            "sync/copy",
            {"srcFs": src_fs, "dstFs": dst_fs, "createEmptySrcDirs": create_empty_src_dirs},
        )

    def copy_async(self, src_fs: str, dst_fs: str, create_empty_src_dirs: bool = False) -> AsyncJobResponse:
        result = self._post(
            "sync/copy",
            {"_async": True, "srcFs": src_fs, "dstFs": dst_fs, "createEmptySrcDirs": create_empty_src_dirs},
        )
        return AsyncJobResponse.from_dict(result)

    def sync(self, src_fs: str, dst_fs: str, create_empty_src_dirs: bool = False) -> None:
        self._post(
            "sync/sync",
            {"srcFs": src_fs, "dstFs": dst_fs, "createEmptySrcDirs": create_empty_src_dirs},
        )

    def sync_async(self, src_fs: str, dst_fs: str, create_empty_src_dirs: bool = False) -> AsyncJobResponse:
        result = self._post(
            "sync/sync",
            {"_async": True, "srcFs": src_fs, "dstFs": dst_fs, "createEmptySrcDirs": create_empty_src_dirs},
        )
        return AsyncJobResponse.from_dict(result)

    def publiclink(self, fs: str, remote: str, unlink: bool = False, expire: str | None = None) -> None:
        self._post(
            "operations/publiclink",
            {"fs": fs, "remote": remote, "unlink": unlink, **({"expire": expire} if expire else {})},
        )

    # -------------------------
    # Utilities
    # -------------------------
    def job_status(self, jobid: int) -> JobStatus:
        return JobStatus.from_dict(self._post("job/status", {"jobid": jobid}))

    def job_list(self) -> JobList:
        return JobList.from_dict(self._post("job/list"))

    def abort_job(self, jobid: int) -> None:
        self._post("job/stop", {"jobid": jobid})

    def abort_jobgroup(self, group: str) -> None:
        self._post("job/stopgroup", {"group": group})

    def core_stats(self) -> CoreStats:
        return CoreStats.from_dict(self._post("core/stats"))

    def version(self) -> CoreVersion:
        return CoreVersion.from_dict(self._post("core/version"))

    def config_listremotes(self) -> ConfigListremotes:
        return ConfigListremotes.from_dict(self._post("config/listremotes"))

    def operational(self) -> bool:
        chk_input = {"op": True}
        try:
            return self._noopauth(chk_input) == chk_input
        except Exception:
            return False


# if __name__ == "__main__":
#     client = RcloneClient()

#     # print(client.version())
#     # print(client.job_list())
#     # print(client.core_stats())
#     # print(client.config_listremotes())
#     # print(client.alive())

#     print(
#         client.sync(
#             "media",
#             f"{'localremote'.rstrip(':')}:{'tmp/subdir_api-sync'.rstrip('/')}/",
#         )
#     )

#     print(
#         client.copyfile(
#             str(Path.cwd().absolute()),
#             "userdata/private.css",
#             f"{'localremote'.rstrip(':')}:",
#             f"{'tmp/copyfile'.rstrip('/')}/priv.css",
#         )
#     )

#     print(
#         client.copyfile(
#             str(Path.cwd().absolute()),
#             "userdata/private.css",
#             f"{'localremote'.rstrip(':')}:",
#             f"{'tmp/copyfile'.rstrip('/')}/private.css",
#         )
#     )

#     # print(
#     #     client.copy(
#     #         "media",
#     #         f"{'localremote'.rstrip(':')}:{'tmp/subdir_api-copy'.rstrip('/')}/",
#     #     )
#     # )

#     copyjob = client.copyfile_async(
#         "/home/michael/dev/photobooth/photobooth-app/",  # local files seems need to be absolute?! but this is not true for sync?!
#         "src/web/download/index.html",
#         f"{'localremote'.rstrip(':')}:",
#         f"{'tmp/subdir_api'.rstrip('/')}/index.html",
#     )
#     # print(copyjob)
#     # print(client.job_status(copyjob.jobid))
#     # print(client.core_stats())
#     # time.sleep(1)
#     # print(client.job_status(copyjob.jobid))
#     # print(client.core_stats())

#     # last_job = max(client.job_list().jobids)
#     # print(client.job_status(last_job))

#     # try:
#     #     print(client._post("rc/error"))
#     # except RcloneProcessException as exc:
#     #     print("got error")
#     #     print(exc)
#     # try:
#     #     print(client._post("rc/fatal"))
#     # except RcloneProcessException as exc:
#     #     print("got fatal err")
#     #     print(exc.status)

#     # print(client._post("rc/list"))
#     print(client._post("options/local", {"input": "test", "_config": {"BwLimit": "1000K"}})["config"]["BwLimit"])
#     print(client._post("options/local", {"input": "test", "_config": {"BwLimit": "1000K"}})["config"]["BwLimit"])
