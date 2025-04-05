import logging
from glob import glob
from pathlib import Path

from fastapi import APIRouter

from ... import USERDATA_PATH
from ...utils.enumerate import serial_ports, webcameras
from ...utils.helper import filenames_sanitize

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enumerate", tags=["admin", "enumerate"])


@router.get("/serialports")
def api_get_serial_ports() -> list[str]:
    return serial_ports()


@router.get("/usbcameras")
def api_get_usbcameras() -> list[str]:
    return webcameras()


@router.get("/userfiles")
def get_search(q: str = "") -> list[str]:
    search_pattern = f"*{q}*" if q else ""
    sanitized_input = filenames_sanitize(f"{USERDATA_PATH}**/{search_pattern}").relative_to(Path.cwd())

    return [result for result in sorted(glob(str(sanitized_input), recursive=True)) if Path(result).is_file()]
