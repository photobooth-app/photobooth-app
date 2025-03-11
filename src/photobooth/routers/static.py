import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from .. import USERDATA_PATH

logger = logging.getLogger(__name__)
static_router = APIRouter(tags=["static"])


@static_router.get("/")
def index():
    """
    return homepage of booth
    """
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate"}
    return FileResponse(path=Path(__file__).parent.parent.joinpath("web_spa", "index.html").resolve(), headers=headers)


@static_router.get("/private.css")
def ui_private_css():
    """
    if private.css exists return the file content, otherwise send empty response to avoid 404
    """
    path = Path(USERDATA_PATH, "private.css")
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate"}
    if not path.is_file():
        return Response("/* placeholder. create private.css in userdata folder to customize css */", headers=headers)
    else:
        return FileResponse(path=path, headers=headers)
