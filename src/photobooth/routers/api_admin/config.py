import logging
from typing import Any, AnyStr

from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError
from pydantic_core import ValidationError

from ...container import container
from ...services.config.baseconfig import SchemaTypes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["admin", "config"])


@router.get("/list")
def api_get_configurables():
    return container.config_service.list_configurables()


@router.delete("")
def api_reset_all_config():
    raise NotImplementedError


@router.delete("/{configurable}")
def api_reset_config(configurable: str):
    container.config_service.reset(configurable)


@router.get("/{configurable}/schema")
def api_get_config_schema(configurable: str, schema_type: SchemaTypes = "default"):
    return container.config_service.get_schema(configurable, schema_type)


@router.get("/{configurable}")
def api_get_config_current_active(configurable: str):
    return container.config_service.get_current(configurable, True)


@router.patch("/{configurable}")
def api_post_config_current(configurable: str, updated_config: dict[AnyStr, Any], reload: bool = False):
    """Update the configuration for appconfig (configurable=app) or a plugin (example configurable="photobooth.plugins.gpio_lights")
    The configuration is persisted also after update.
    updated_config is a generic type valid to receive json objects instead of a pydantic model because depending on the configurable
    the model is different.

    Args:
        configurable (str): app for appconfig, otherwise str with plugin name to update the config for. Defaults to None.
        updated_config (dict[AnyStr, Any]): valid json that is validated against appconfig or plugin config pydantic models
    """

    # persists also automatically
    try:
        container.config_service.validate_and_set_current_and_persist(configurable, updated_config)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    if reload:
        logger.info("reload paramter is set, so all registered services are reloaded now. This may take some time...")
        container.reload()
