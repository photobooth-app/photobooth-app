import json
import logging
import subprocess
from collections.abc import Callable
from functools import wraps
from shutil import which

logger = logging.getLogger(__name__)


class RcloneException(ChildProcessError):
    def __init__(self, description: str, error_msg: str):
        self.description = description
        self.error_msg = error_msg
        super().__init__(f"{description}. Error message: \n{error_msg}")


def __check_installed(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not is_installed():
            raise Exception("rclone is not installed on this system. Please install it from here: https://rclone.org/")

        return func(*args, **kwargs)

    return wrapper


def is_installed() -> bool:
    return which("rclone") is not None


@__check_installed
def version() -> str:
    stdout, stderr = __rclone_cmd_operation(["version"])

    return stdout.splitlines()[0].replace("rclone ", "")


@__check_installed
def get_remotes() -> list[str]:
    """
    :return: A list of all available remotes.
    """
    stdout, _ = __rclone_cmd_operation(["listremotes"])
    remotes = stdout.split()
    if remotes is None:
        remotes = []

    return remotes


@__check_installed
def copy(src_path: str, dest_path: str, ignore_existing=False, callback: Callable[[dict], None] | None = None, args=None) -> subprocess.Popen:
    return __rclone_transfer_operation(src_path, dest_path, ignore_existing=ignore_existing, subcommand="copy", args=args, callback=callback)


@__check_installed
def sync(src_path: str, dest_path: str, callback: Callable[[dict], None] | None = None, args=None) -> subprocess.Popen:
    return __rclone_transfer_operation(src_path, dest_path, subcommand="sync", args=args, callback=callback)


@__check_installed
def delete(path: str, args=None):
    if args is None:
        args = []

    subcommand = ["delete", path]
    print(subcommand)
    # __rclone_cmd_operation(subcommand, args)


def __rclone_transfer_operation(
    src_path: str,
    dest_path: str,
    subcommand: str,
    ignore_existing=False,
    args: list[str] | None = None,
    callback: Callable[[dict], None] | None = None,
):
    print(f"{subcommand} {src_path} to {dest_path}")

    # add optional arguments and flags to the command
    full_command = ["rclone", subcommand]

    # add global rclone flags
    if ignore_existing:
        full_command += [" --ignore-existing"]

    full_command += [src_path]
    full_command += [dest_path]
    full_command += ["--stats", "0.25s"]
    full_command += ["--stats-unit", "bytes"]
    full_command += ["--use-json-log"]
    full_command += ["-v"]

    # optional named arguments/flags
    if args:
        full_command += args

    logger.debug(f"Running command: {full_command}")

    # try:
    #     process = subprocess.run(full_command, capture_output=True, check=True)
    # except subprocess.CalledProcessError as exc:
    #     msg = f'Rclone "{subcommand}" command failed'
    #     if args:
    #         msg += f'with args "{args}"'

    #     raise RcloneException(msg, exc.stderr) from exc

    process = subprocess.Popen(full_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert process.stderr
    for line in process.stderr:
        # if self._stop_requested:
        #     self.abort()
        #     break

        line = line.strip()
        if not line:
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # ignore non-JSON lines

        if callback:
            callback(event)

    return process


def abort(process: subprocess.Popen):
    """Abort the running rclone process."""
    if process and process.poll() is None:
        process.terminate()


def __rclone_cmd_operation(subcommand: list[str], args: list[str] | None = None, shell=True, encoding="utf-8") -> tuple[str, str]:
    # Set the config path if defined by the user,
    # otherwise the default rclone config path is used:
    if args is None:
        args = []

    # add optional arguments and flags to the command
    full_command = ["rclone"]
    full_command += subcommand
    full_command += args

    logger.debug(f"Running command: {full_command}")

    try:
        process = subprocess.run(full_command, shell=shell, encoding=encoding, capture_output=True, check=True)
    except subprocess.CalledProcessError as exc:
        msg = f'Rclone "{subcommand}" command failed'
        if len(args) > 0:
            msg += f'with args "{args}"'

        raise RcloneException(msg, exc.stderr) from exc

    return process.stdout, process.stderr
