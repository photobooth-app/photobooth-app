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

    def save(self):
        appconfig.persist()
        self._pms.pm.hook.persist()

    def reset(self):
        appconfig.deleteconfig()
        self._pms.pm.hook.deleteconfig()

    def list_configurable_plugins(self) -> list[str]:
        return self._pms.list_configurable_plugins()

    def _get_appconfig_or_pluginconfig(self, plugin_name: str) -> BaseConfig:
        if not plugin_name:
            return appconfig
        else:
            plugin = self._pms.pm.get_plugin(plugin_name)
            if not plugin:
                raise RuntimeError(f"plugin_name {plugin_name} not found!")

            if not self._pms.is_configurable_plugin(plugin):
                raise RuntimeError(f"{plugin_name} has no configuration!")

            return self._pms.get_plugin_configuration(plugin)

    def get_schema(self, schema_type: SchemaTypes = "default", plugin_name: str = None):
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(plugin_name)
        return appconfig_or_plugin_config.get_schema(schema_type=schema_type)

    def get_current(self, secrets_is_allowed: bool = False, plugin_name: str = None) -> dict[str, Any]:
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(plugin_name)
        return appconfig_or_plugin_config.get_current(secrets_is_allowed=secrets_is_allowed)

    def set_current(self, updated_config: dict[AnyStr, Any], plugin_name: str = None):
        appconfig_or_plugin_config = self._get_appconfig_or_pluginconfig(plugin_name)

        updated_config_validated = appconfig_or_plugin_config.model_validate(updated_config)
        appconfig_or_plugin_config.__dict__.update(updated_config_validated)

        self.save()
