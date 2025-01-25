"""
Utilities
"""

import os
import platform
from pathlib import Path


def filenames_sanitize(path_str: str) -> Path:
    """turn strings in paths and sanitize. Used for userinput to check the path is below CWD.

    Args:
        filenames (list[str]): _description_

    Raises:
        ValueError: _description_

    Returns:
        list[Path]: _description_
    """
    basepath = str(Path.cwd())
    fullpath = os.path.normpath(os.path.join(basepath, path_str))

    if not fullpath.startswith(basepath):
        raise ValueError(f"illegal file requested: {fullpath}")

    return Path(fullpath)


def get_user_file(filepath: Path | str) -> Path:
    """function to check if a file exists in the user directory or in the demoassets directory
    if it exists in the user directory, return the user directory path, else return the demoassets path
    used by the pipelines and also by the API to serve files
    from API as well as internal the filepath is /userdata/path/to/file

    """

    file_user_path = Path(filepath)
    file_demoassets_path = Path(__file__).parent.parent.resolve().joinpath(Path("demoassets", filepath))

    out_filepath = file_user_path if file_user_path.is_file() else file_demoassets_path

    if not out_filepath.is_file():
        raise FileNotFoundError(f"filepath {str(filepath)} not found!")

    return out_filepath


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
