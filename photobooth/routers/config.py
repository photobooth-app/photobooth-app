import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from ..appconfig import AppConfig
from ..containers import ApplicationContainer

logger = logging.getLogger(__name__)
config_router = APIRouter(
    prefix="/config",
    tags=["config"],
)


@config_router.get("/ui")
@inject
def index(
    config: AppConfig = Depends(Provide[ApplicationContainer.config]),
):
    """get part of the config dedicated for UI only. UI requests this on startup"""
    return config.uisettings
