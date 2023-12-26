import logging

from dependency_injector.wiring import inject
from fastapi import APIRouter

from ...services.config import AppConfig, appconfig

logger = logging.getLogger(__name__)
admin_config_router = APIRouter(
    prefix="/admin/config",
    tags=["admin", "config"],
)


@admin_config_router.get("/schema")
def api_get_config_schema(schema_type: str = "default"):
    """
    Get schema to build the client UI
    :param str schema_type: default or dereferenced.
    """
    return appconfig.get_schema(schema_type=schema_type)


@admin_config_router.get("/reset")
@inject
def api_reset_config():
    """
    Reset config, deleting config.json file

    """
    appconfig.deleteconfig()  #  delete file


@admin_config_router.get("/currentActive")
@inject
def api_get_config_current_active():
    """returns currently cached and active settings"""
    return appconfig


@admin_config_router.get("/current")
def api_get_config_current():
    """read settings from drive and return"""
    return AppConfig()


@admin_config_router.post("/current")
@inject
def api_post_config_current(
    updated_config: AppConfig,
):
    # save settings to disc
    updated_config.persist()

    # update central config to make new config avail immediately
    # pay attention: dict is overwritten directly, so updated_config needs to be validated (which it is)
    appconfig.__dict__.update(updated_config)

    # appcontainer.shutdown_resources()
    # appcontainer.init_resources()
