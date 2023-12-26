import logging

from dependency_injector.wiring import inject
from fastapi import APIRouter

from ..services.config import appconfig

logger = logging.getLogger(__name__)
config_router = APIRouter(
    prefix="/config",
    tags=["config"],
)


@config_router.get("/ui")
@inject
def index():
    """get part of the config dedicated for UI only. UI requests this on startup"""
    return appconfig.uisettings
