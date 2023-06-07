import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)
home_router = APIRouter(
    tags=["home"],
)

"""
@home_router.get("/")
async def redirect_web():
    response = RedirectResponse(url="/web/")
    return response
"""


@home_router.get("/")
def index():
    """
    return homepage of booth
    """
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate"}
    return FileResponse(path=Path(__file__).parent.parent.joinpath("web_spa", "index.html").resolve(), headers=headers)
