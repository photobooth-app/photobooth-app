import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

logger = logging.getLogger(__name__)
log_router = APIRouter(
    prefix="/log",
    tags=["logs"],
)


@log_router.get("/latest")
async def get_latest_log():
    """provide latest logfile to download
    TODO Handle exception if file not exists

    Returns:
        _type_: _description_
    """

    # might be a bug in fastapi: if file changes after file length determined
    # for header content-length, the browser rejects loading the file.
    # return FileResponse(path="./log/qbooth.log")

    return Response(
        content=Path("./log/qbooth.log").read_text(encoding="utf-8"),
        media_type="text/plain",
    )
