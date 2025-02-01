import logging

from .base import BaseService
from .config import appconfig
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
