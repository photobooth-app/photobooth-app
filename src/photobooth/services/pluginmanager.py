import logging
from typing import cast

from pluggy import PluginManager

from ..plugins import pm as pluggy_pm
from ..plugins.base_plugin import BaseConfig, BasePlugin
from .base import BaseService

logger = logging.getLogger(__name__)


class PluginManagerService(BaseService):
    def __init__(self):
        super().__init__()

        # use central singleton pluggy pluginmanager
        self.pm: PluginManager = pluggy_pm

        logger.info(f"registered plugins: {self.list_plugins()}")

        self.pm.hook.init()

    def start(self):
        """When the pluginmanager is started, it will start all registered plugins that have the start hook registered"""
        super().start()

        self.pm.hook.start()

        super().started()

    def stop(self):
        """When the pluginmanager is stoppped, it will stop all registered plugins that have the stop hook registered"""
        super().stop()

        self.pm.hook.stop()

        super().stopped()

    def get_plugin(self, plugin_name: str) -> BasePlugin[BaseConfig]:
        _plugin = self.pm.get_plugin(plugin_name)

        if not _plugin:
            raise ValueError(f"there is no plugin with name '{plugin_name}'!")

        return _plugin

    def list_plugins(self) -> list[str]:
        plugins: list[str] = []

        for name, _ in self.pm.list_name_plugin():
            plugins.append(name)

        return plugins

    @staticmethod
    def is_configurable_plugin(plugin: BasePlugin[BaseConfig]) -> bool:
        try:
            plugin._config.get_current()
        except AttributeError:
            return False
        else:
            return True

    @staticmethod
    def get_plugin_configuration(plugin: BasePlugin[BaseConfig]) -> BaseConfig:
        return plugin._config

    def list_configurable_plugins(self) -> list[str]:
        configurable_plugins: list[str] = []

        for name, plugin in self.pm.list_name_plugin():
            if self.is_configurable_plugin(cast(BasePlugin[BaseConfig], plugin)):
                configurable_plugins.append(name)

        return configurable_plugins
