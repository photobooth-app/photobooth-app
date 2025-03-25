"""
Utilities
"""

import logging
import os
import platform
from pathlib import Path

logger = logging.getLogger(__name__)


def filenames_sanitize(path: Path | str, basepath: Path = Path.cwd()) -> Path:
    """turn strings in paths and sanitize. Used for userinput to check the path is below CWD.

    Args:
        filenames (list[str]): _description_

    Raises:
        ValueError: _description_

    Returns:
        list[Path]: _description_
    """
    path_str = str(path)
    basepath_str = str(basepath)
    fullpath = os.path.normpath(os.path.join(basepath_str, path_str))

    if not fullpath.startswith(basepath_str):
        raise ValueError(f"illegal file requested: {fullpath}")

    return Path(fullpath)


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
