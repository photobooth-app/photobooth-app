"""
Utilities
"""
import os
import platform
from pathlib import Path
from typing import Union

DATA_USER_PATH = "./userdata/"


def get_user_file(filepath: Union[Path, str]) -> Path:
    # check font is avail, otherwise send pipelineerror - so we can recover and continue
    # default font Roboto comes with app, fallback to that one if avail
    file_user_path = Path(DATA_USER_PATH, filepath)
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
