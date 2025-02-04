import logging
from typing import Any, AnyStr

from fastapi import APIRouter

from ...container import container
from ...services.config.baseconfig import SchemaTypes

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/config",
    tags=["admin", "config"],
)


@router.get("/schema")
def api_get_config_schema(schema_type: SchemaTypes = "default", plugin_name: str = None):
    return container.config_service.get_schema(schema_type=schema_type, plugin_name=plugin_name)


@router.get("/reset")
def api_reset_config():
    container.config_service.reset()


@router.get("/current")
def api_get_config_current_active(plugin_name: str = None):
    return container.config_service.get_current(secrets_is_allowed=True, plugin_name=plugin_name)


@router.post("/current")
def api_post_config_current(updated_config: dict[AnyStr, Any], plugin_name: str = None):
    """Update the configuration for appconfig (plugin_name=None) or a plugin (example plugin_name="photobooth.plugins.gpio_lights")
    The configuration is persisted also after update.
    updated_config is a generic type valid to receive json objects instead of a pydantic model because depending on the plugin_name the model is different.

    Args:
        updated_config (dict[AnyStr, Any]): valid json that is validated against appconfig or plugin config pydantic models
        plugin_name (str, optional): None for appconfig, otherwise str with plugin name to update the config for. Defaults to None.
    """

    # persists also automatically
    container.config_service.set_current(updated_config, plugin_name=plugin_name)
