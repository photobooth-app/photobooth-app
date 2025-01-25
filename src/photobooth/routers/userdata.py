import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import USERDATA_PATH
from ..utils.helper import get_user_file

logger = logging.getLogger(__name__)
userdata_router = APIRouter(
    prefix="/userdata",
    tags=["userdata"],
)


@userdata_router.get("/{filepath:path}")
def api_get_userfiles(filepath: Path):
    try:
        return FileResponse(path=get_user_file(Path(USERDATA_PATH) / filepath))
    except FileNotFoundError as exc:
        logger.warning(f"cannot find {filepath}")
        raise HTTPException(status_code=404, detail=f"cannot find {filepath}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc
