import logging
from typing import Any, AnyStr

from .base import BaseService
from .config import appconfig
from .config.baseconfig import BaseConfig, SchemaTypes
from .pluginmanager import PluginManagerService

logger = logging.getLogger(__name__)


class ConfigurationService(BaseService):
    def __init__(self, pluginmanager_service: PluginManagerService):
        super().__init__()

        self._pms = pluginmanager_service

    def save(self, plugin_name: str):
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(plugin_name)
        appconfig_or_plugin_config.persist()

    def reset(self, plugin_name: str):
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(plugin_name)
        appconfig_or_plugin_config.deleteconfig()
        appconfig_or_plugin_config.reset_defaults()

    def list_configurables(self) -> list[str]:
        configurable_elements = ["app"] + self._pms.list_configurable_plugins()
        return configurable_elements

    def get_schema(self, schema_type: SchemaTypes = "default", plugin_name: str = None):
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(plugin_name)
        return appconfig_or_plugin_config.get_schema(schema_type=schema_type)

    def get_current(self, secrets_is_allowed: bool = False, plugin_name: str = None) -> dict[str, Any]:
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(plugin_name)
        return appconfig_or_plugin_config.get_current(secrets_is_allowed=secrets_is_allowed)

    def validate_and_set_current_and_persist(self, updated_config: dict[AnyStr, Any], plugin_name: str = None):
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(plugin_name)
        updated_config_validated = appconfig_or_plugin_config.model_validate(updated_config)
        appconfig_or_plugin_config.__dict__.update(updated_config_validated)

        appconfig_or_plugin_config.persist()

    def _get_appconfig_or_pluginconfig(self, plugin_name: str) -> BaseConfig:
        if not plugin_name:
            raise ValueError("no configurable given, cannot get config.")

        if plugin_name == "app":  # None or "" evals to False
            return appconfig
        else:
            plugin = self._pms.pm.get_plugin(plugin_name)
            if not plugin:
                raise FileNotFoundError(f"plugin_name {plugin_name} not found!")

            if not self._pms.is_configurable_plugin(plugin):
                raise RuntimeError(f"{plugin_name} has no configuration!")

            return self._pms.get_plugin_configuration(plugin)
