import locale
import os
from pathlib import Path

# set locale to systems default
locale.setlocale(locale.LC_ALL, "")

# database
DATABASE_PATH = "./database/"
# mediaitems cache for resized versions
CACHE_PATH = "./cache/"
# media collection files
MEDIA_PATH = "./media/"
PATH_UNPROCESSED = "".join([MEDIA_PATH, "unprocessed_original/"])
PATH_PROCESSED = "".join([MEDIA_PATH, "processed_full/"])
# folder not touched, used by user
USERDATA_PATH = "./userdata/"
# logfiles
LOG_PATH = "./log/"
# configuration
CONFIG_PATH = "./config/"
# all other stuff that is used temporarily
TMP_PATH = "./tmp/"
# recycle dir if delete moves to recycle instead actual removing
RECYCLE_PATH = "./recycle/"


def _create_basic_folders():
    os.makedirs(DATABASE_PATH, exist_ok=True)
    os.makedirs(CACHE_PATH, exist_ok=True)
    os.makedirs(MEDIA_PATH, exist_ok=True)
    os.makedirs(PATH_UNPROCESSED, exist_ok=True)
    os.makedirs(PATH_PROCESSED, exist_ok=True)
    os.makedirs(USERDATA_PATH, exist_ok=True)
    os.makedirs(LOG_PATH, exist_ok=True)
    os.makedirs(CONFIG_PATH, exist_ok=True)
    os.makedirs(TMP_PATH, exist_ok=True)
    os.makedirs(RECYCLE_PATH, exist_ok=True)


def _copy_demo_assets_to_userdata():
    src_path = Path(__file__).parent.resolve().joinpath("demoassets/userdata")
    dst_path = Path(USERDATA_PATH, "demoassets")

    if not dst_path.exists():
        os.symlink(src_path, dst_path, target_is_directory=True)
    elif dst_path.is_symlink():
        return
    else:
        raise RuntimeError(f"error setup demoassets, {dst_path} exists but is no symlink!")


try:
    _create_basic_folders()
    _copy_demo_assets_to_userdata()
except Exception as exc:
    raise RuntimeError(f"cannot initialize data folders, error: {exc}") from exc
