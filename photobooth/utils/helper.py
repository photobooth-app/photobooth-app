"""
Utilities
"""
import os
import platform
from pathlib import Path
from typing import Union


def filenames_sanitize(filenames: list[str], check_exists: bool = True) -> list[Path]:
    # convert filenames (usually strings) to path objects and resolve to normalize.
    # also remove leading / because we handle everything relative
    paths = [Path(p.lstrip("/")).resolve() for p in filenames]

    # preflight checks:
    for path in paths:
        # check for path traversal:
        # only allow files to be zipped below CWD which is the datadir.
        if not path.is_relative_to(Path.cwd()):
            raise ValueError(f"illegal file requested: {path}")

        # path exists:
        if check_exists and not path.exists():
            raise FileNotFoundError(f"path does not exist: {path}")

    return paths


def get_user_file(filepath: Union[Path, str]) -> Path:
    # check font is avail, otherwise send pipelineerror - so we can recover and continue
    # default font Roboto comes with app, fallback to that one if avail
    file_user_path = Path(filepath)
    file_assets_path = Path(__file__).parent.parent.resolve().joinpath(Path("assets", filepath))
    out_filepath = file_user_path if file_user_path.is_file() else file_assets_path

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
