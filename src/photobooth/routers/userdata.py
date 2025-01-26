import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import USERDATA_PATH
from ..utils.helper import filenames_sanitize, get_user_file

logger = logging.getLogger(__name__)
userdata_router = APIRouter(
    prefix="/userdata",
    tags=["userdata"],
)


@userdata_router.get("/{filepath:path}")
def api_get_userfiles(filepath: str):
    try:
        filepath_sanitized = filenames_sanitize(f"{USERDATA_PATH}{filepath}")
        return FileResponse(path=get_user_file(filepath_sanitized))
    except FileNotFoundError as exc:
        logger.warning(f"cannot find {filepath}")
        raise HTTPException(status_code=404, detail=f"cannot find {filepath}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc
