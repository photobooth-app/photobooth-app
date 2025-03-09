import logging
from typing import Any, AnyStr

from ..appconfig import appconfig
from .base import BaseService
from .config.baseconfig import BaseConfig, SchemaTypes
from .pluginmanager import PluginManagerService

logger = logging.getLogger(__name__)


class ConfigurationService(BaseService):
    def __init__(self, pluginmanager_service: PluginManagerService):
        super().__init__()

        self._pms = pluginmanager_service

    def save(self, configurable: str):
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(configurable)
        appconfig_or_plugin_config.persist()

    def reset(self, configurable: str):
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(configurable)
        appconfig_or_plugin_config.deleteconfig()
        appconfig_or_plugin_config.reset_defaults()

    def list_configurables(self) -> list[str]:
        configurable_elements = ["app"] + self._pms.list_configurable_plugins()
        return configurable_elements

    def get_schema(self, configurable: str, schema_type: SchemaTypes = "default"):
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(configurable)
        return appconfig_or_plugin_config.get_schema(schema_type=schema_type)

    def get_current(self, configurable: str, secrets_is_allowed: bool = False) -> dict[str, Any]:
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(configurable)
        return appconfig_or_plugin_config.get_current(secrets_is_allowed=secrets_is_allowed)

    def validate_and_set_current_and_persist(self, configurable: str, updated_config: dict[AnyStr, Any]):
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(configurable)
        updated_config_validated = appconfig_or_plugin_config.model_validate(updated_config)
        appconfig_or_plugin_config.__dict__.update(updated_config_validated)

        appconfig_or_plugin_config.persist()

    def _get_appconfig_or_pluginconfig(self, configurable: str) -> BaseConfig:
        if not configurable:
            raise ValueError("no configurable given, cannot get config.")

        if configurable == "app":  # None or "" evals to False
            return appconfig
        else:
            plugin = self._pms.get_plugin(configurable)

            if not self._pms.is_configurable_plugin(plugin):
                raise RuntimeError(f"plugin {configurable} has no configuration!")

            return self._pms.get_plugin_configuration(plugin)
