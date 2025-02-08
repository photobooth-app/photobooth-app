import logging
from typing import Any, AnyStr

from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError
from pydantic_core import ValidationError

from ...container import container
from ...services.config.baseconfig import SchemaTypes

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/config",
    tags=["admin", "config"],
)


@router.get("/list")
def api_get_configurables():
    return container.config_service.list_configurables()


@router.delete("")
def api_reset_all_config():
    container.config_service.reset_all()


@router.delete("/{plugin_name}")
def api_reset_config(plugin_name: str):
    container.config_service.reset(plugin_name=plugin_name)


@router.get("/{plugin_name}/schema")
def api_get_config_schema(plugin_name: str, schema_type: SchemaTypes = "default"):
    return container.config_service.get_schema(schema_type=schema_type, plugin_name=plugin_name)


@router.get("/{plugin_name}")
def api_get_config_current_active(plugin_name: str = None):
    return container.config_service.get_current(secrets_is_allowed=True, plugin_name=plugin_name)


@router.patch("/{plugin_name}")
def api_post_config_current(updated_config: dict[AnyStr, Any], plugin_name: str):
    """Update the configuration for appconfig (plugin_name=None) or a plugin (example plugin_name="photobooth.plugins.gpio_lights")
    The configuration is persisted also after update.
    updated_config is a generic type valid to receive json objects instead of a pydantic model because depending on the plugin_name
    the model is different.

    Args:
        updated_config (dict[AnyStr, Any]): valid json that is validated against appconfig or plugin config pydantic models
        plugin_name (str, optional): None for appconfig, otherwise str with plugin name to update the config for. Defaults to None.
    """

    # persists also automatically
    try:
        container.config_service.validate_and_set_current_and_persist(updated_config, plugin_name)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
