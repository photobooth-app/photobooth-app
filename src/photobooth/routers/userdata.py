import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import USERDATA_PATH
from ..utils.helper import filenames_sanitize

logger = logging.getLogger(__name__)
userdata_router = APIRouter(prefix="/userdata", tags=["userdata"])


@userdata_router.get("/{filepath:path}")
def api_get_userfiles(filepath: str):
    try:
        if filepath == "demoassets" or filepath.startswith("demoassets/"):
            demoassets_path = Path(__file__).resolve().parents[1] / "demoassets" / "userdata"
            file_out = filenames_sanitize(filepath.removeprefix("demoassets/"), demoassets_path)
        else:
            file_out = filenames_sanitize(filepath, Path(USERDATA_PATH))

        if not file_out.is_file():
            raise FileNotFoundError(f"{filepath} not found")

        return FileResponse(path=file_out)
    except FileNotFoundError as exc:
        logger.warning(f"cannot find {filepath}", exc_info=exc)
        raise HTTPException(status_code=404, detail=f"cannot find {filepath}") from exc
    except ValueError as exc:
        logger.warning(f"illegal file requested: {filepath}", exc_info=exc)
        raise HTTPException(status_code=400, detail=f"illegal file requested: {filepath}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc
