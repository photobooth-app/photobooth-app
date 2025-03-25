import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import USERDATA_PATH
from ..utils.helper import filenames_sanitize

logger = logging.getLogger(__name__)
userdata_router = APIRouter(prefix="/userdata", tags=["userdata"])


@userdata_router.get("/{filepath:path}")
def api_get_userfiles(filepath: str):
    try:
        file_out = filenames_sanitize(f"{USERDATA_PATH}{filepath}")
        if not file_out.is_file():
            raise FileNotFoundError(f"{filepath} not found")

        return FileResponse(path=file_out)
    except FileNotFoundError as exc:
        logger.warning(exc)
        logger.warning(f"cannot find {filepath}")
        raise HTTPException(status_code=404, detail=f"cannot find {filepath}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc
