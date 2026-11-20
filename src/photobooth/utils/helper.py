"""
Utilities
"""

import logging
import os
import platform
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def filename_str_time() -> str:
    """whenever somewhere a filename needs to be generated, rely on this function. it gives "almost" unique filenames
    that reflect time history so later users can review captures easily and it's sorted by time.

    Returns:
        str: _description_
    """
    return datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")


def filenames_sanitize(path: Path | str, basepath: Path = Path.cwd()) -> Path:
    """turn strings in paths and sanitize. Used for userinput to check the path is below CWD."""

    base = os.path.realpath(basepath)
    fullpath = os.path.realpath(os.path.join(base, path))

    base_normalized = os.path.normcase(base)
    fullpath_normalized = os.path.normcase(fullpath)
    base_prefix = base_normalized if base_normalized.endswith(os.sep) else base_normalized + os.sep
    if fullpath_normalized != base_normalized and not fullpath_normalized.startswith(base_prefix):
        raise ValueError(f"illegal file requested: {fullpath} using basepath {base}")

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
