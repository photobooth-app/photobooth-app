import logging

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
    return FileResponse(path="web/index.html", headers=headers)
