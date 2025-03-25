import logging
import logging.config
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ... import LOG_PATH

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["logs"])


@router.get("/log/latest")
async def get_log_latest():
    """provide latest logfile to download"""

    log_dir = Path(LOG_PATH)
    list_of_paths = log_dir.glob("*.log")
    latest_path = max(list_of_paths, key=lambda p: p.stat().st_mtime)
    logger.info(f"getting latest logfile: {latest_path}")

    try:
        return Response(content=latest_path.read_text(encoding="utf-8"), media_type="text/plain")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="error getting log") from exc
