import importlib
import logging
import pkgutil
import sys

import pluggy

from ..plugins import hookspecs
from .base import BaseService

logger = logging.getLogger(__name__)


hookimpl = pluggy.HookimplMarker("photobooth-app")


class PluginManagerService(BaseService):
    def __init__(self):
        super().__init__()

        # create a manager and add the spec
        self.pm = pluggy.PluginManager("photobooth-app")
        self.pm.add_hookspecs(hookspecs)

        #  register plugins
        # internal predefined plugins that come with the app
        number_registered_plugins = self.pm.load_setuptools_entrypoints("pluggable")
        logger.info(f"registered {number_registered_plugins} internal plugins: {[names[0] for names in self.pm.list_name_plugin()]}")

        #  register plugins
        # user plugins
        sys.path.append("./plugins/")
        discovered_userplugins = [importlib.import_module(name) for finder, name, ispkg in pkgutil.iter_modules(["./plugins/"])]
        logger.info(f"discovered {len(discovered_userplugins)} user plugins: {[plugin.__name__ for plugin in discovered_userplugins]}")
        for discovered_userplugin in discovered_userplugins:
            self.pm.register(discovered_userplugin)

        # all registered plugins
        logger.info(f"finally registered plugins: {[names[0] for names in self.pm.list_name_plugin()]}")

        res = self.pm.hook.init(arg1=1, arg2=2)
        print(res)

    def start(self):
        super().start()

        self.pm.hook.start()

        super().started()

    def stop(self):
        super().stop()

        self.pm.hook.stop()

        super().stopped()
