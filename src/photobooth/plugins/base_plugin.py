from photobooth.services.config.baseconfig import BaseConfig

from .hookspecs import hookimpl


class BasePlugin:
    def __init__(self):
        self._config: BaseConfig = None

    @hookimpl
    def persist(self):
        print("SAVE PLUGIN CONFIG")
        if self._config:
            self._config.persist()

    @hookimpl
    def deleteconfig(self):
        print("delete PLUGIN CONFIG")
        if self._config:
            self._config.deleteconfig()

    @hookimpl
    def reset(self):
        pass
