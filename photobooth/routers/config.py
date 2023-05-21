import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from ..appconfig import AppConfig
from ..containers import ApplicationContainer
from ..services.systemservice import SystemService

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


@config_router.get("/schema")
def api_get_config_schema(schema_type: str = "default"):
    """
    Get schema to build the client UI
    :param str schema_type: default or dereferenced.
    """
    return AppConfig().get_schema(schema_type=schema_type)


@config_router.get("/reset")
@inject
def api_reset_config(
    config: AppConfig = Depends(Provide[ApplicationContainer.config]),
    system_service: SystemService = Depends(
        Provide[ApplicationContainer.services.system_service]
    ),
):
    """
    Reset config, deleting config.json file

    """
    config.deleteconfig()  #  delete file
    # restart service to load new config
    system_service.util_systemd_control("restart")


@config_router.get("/currentActive")
@inject
def api_get_config_current_active(
    config: AppConfig = Depends(Provide[ApplicationContainer.config]),
):
    """returns currently cached and active settings"""
    return config


@config_router.get("/current")
def api_get_config_current():
    """read settings from drive and return"""
    return AppConfig().dict()


@config_router.post("/current")
@inject
def api_post_config_current(
    updated_config: AppConfig,
    appcontainer: ApplicationContainer = Depends(Provide[ApplicationContainer]),
    config: AppConfig = Depends(Provide[ApplicationContainer.config]),
):
    # save settings to disc
    updated_config.persist()

    # update central config to make new config avail immediately
    # pay attention: dict is overwritten directly, so updated_config needs to be validated (which it is)
    config.__dict__.update(updated_config)

    appcontainer.shutdown_resources()
    appcontainer.init_resources()
