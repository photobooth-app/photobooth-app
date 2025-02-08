import importlib
import logging
import pkgutil
import sys
from importlib.metadata import entry_points

import pluggy

from ..plugins import hookspecs
from ..plugins.base_plugin import BaseConfig, BasePlugin
from .base import BaseService

logger = logging.getLogger(__name__)


class PluginManagerService(BaseService):
    def __init__(self):
        super().__init__()

        # create a manager and add the spec
        self.pm = pluggy.PluginManager("photobooth-app")
        # self.pm.add_hookspecs(hookspecs)
        self.pm.add_hookspecs(hookspecs.PluginManagementSpec)
        self.pm.add_hookspecs(hookspecs.PluginStatemachineSpec)

        # included predefined and externally installable plugins
        ENTRY_POINT_GROUP = "photobooth.plugins"  # see pyproject.toml section
        entry_points_app = entry_points(group=ENTRY_POINT_GROUP)
        included_plugins = [importlib.import_module(entry_point.value) for entry_point in entry_points_app]
        logger.info(
            f"discovered {len(included_plugins)} plugins by entry point group '{ENTRY_POINT_GROUP}': "
            f" {[plugin.__name__ for plugin in included_plugins]}"
        )

        # user plugins. additionally scan folder below working directlry for quick tinkering
        sys.path.append("./plugins/")
        user_plugins = [importlib.import_module(name) for _, name, ispkg in pkgutil.iter_modules(["./plugins/"]) if ispkg]
        logger.info(f"discovered {len(user_plugins)} user-plugins: {[plugin.__name__ for plugin in user_plugins]} in ./plugins/")

        # register all plugins
        for discovered_plugin in included_plugins + user_plugins:
            plugin_class_factory = str(discovered_plugin.__name__).split(".")[-1].title().replace("_", "")

            try:
                instance = getattr(discovered_plugin, plugin_class_factory)()  # Call the plugins object to instanciate.
            except AttributeError as exc:
                logger.error(
                    f"there is no class {plugin_class_factory} defined in {discovered_plugin.__name__}! "
                    f"The plugin is broken and skipped during initialization. Error: {exc}"
                )
                continue

            self.pm.register(instance, name=discovered_plugin.__name__)  # Register the plugin instance

        logger.info(f"registered plugins: {[name for name, _ in self.pm.list_name_plugin()]}")

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

    def list_plugins(self) -> list[str]:
        plugins: list[str] = []

        for name, _ in self.pm.list_name_plugin():
            plugins.append(name)

        return plugins

    @staticmethod
    def is_configurable_plugin(plugin: BasePlugin) -> bool:
        try:
            plugin.get_current()
        except AttributeError:
            return False
        else:
            return True

    @staticmethod
    def get_plugin_configuration(plugin: BasePlugin) -> BaseConfig:
        return plugin._config

    def list_configurable_plugins(self) -> list[str]:
        configurable_plugins: list[str] = []

        for name, plugin in self.pm.list_name_plugin():
            if self.is_configurable_plugin(plugin):
                configurable_plugins.append(name)

        return configurable_plugins
