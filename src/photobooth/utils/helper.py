"""
Utilities
"""

import logging
import os
import platform
from pathlib import Path

logger = logging.getLogger(__name__)


def filenames_sanitize(path_str: str, basepath: Path = Path.cwd()) -> Path:
    """turn strings in paths and sanitize. Used for userinput to check the path is below CWD.

    Args:
        filenames (list[str]): _description_

    Raises:
        ValueError: _description_

    Returns:
        list[Path]: _description_
    """
    basepath_str = str(basepath)
    fullpath = os.path.normpath(os.path.join(basepath_str, path_str))

    if not fullpath.startswith(basepath_str):
        raise ValueError(f"illegal file requested: {fullpath}")

    return Path(fullpath)


def get_user_file(filepath: Path | str) -> Path:
    """function to check if a file exists in the user directory or in the demoassets directory
    if it exists in the user directory, return the user directory path, else return the demoassets path
    used by the pipelines and also by the API to serve files
    from API as well as internal the filepath is /userdata/path/to/file

    """

    file_user_path = filenames_sanitize(str(filepath))
    if file_user_path.is_file():
        return file_user_path

    # now check to fallback to demoassets
    demoassets_path = Path(__file__).parent.parent.resolve().joinpath("demoassets")

    file_demoassets_path = filenames_sanitize(str(Path(demoassets_path, filepath)), demoassets_path)
    if file_demoassets_path.is_file():
        logger.info(f"file {filepath} found in demoassets {file_demoassets_path}")
        return file_demoassets_path

    raise FileNotFoundError(f"filepath {filepath} not found in {file_user_path} or demoassets {file_demoassets_path}!")


def is_rpi():
    """detect if computer is a raspberry pi (any model)

    Returns:
        bool: true is raspberry pi, false is other
    """
    if platform.system() == "Linux":
        if os.path.isfile("/proc/device-tree/model"):
            with open("/proc/device-tree/model", encoding="utf-8") as file:
                model = file.read()
                return "Raspberry" in model

    return False
