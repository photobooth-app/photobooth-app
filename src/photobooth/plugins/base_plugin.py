import logging

from photobooth.services.config.baseconfig import BaseConfig, SchemaTypes

from .hookspecs import hookimpl

logger = logging.getLogger(__name__)


class BasePlugin:
    def __init__(self):
        self._config: BaseConfig = None

    @hookimpl
    def persist(self):
        if self._config:
            self._config.persist()
            logger.info(f"persisted config for plugin {self.__class__.__name__}")

    @hookimpl
    def deleteconfig(self):
        if self._config:
            self._config.deleteconfig()
            logger.info(f"deleted config for plugin {self.__class__.__name__}")

    @hookimpl
    def get_current(self, secrets_is_allowed: bool = False):
        if self._config:
            logger.info(f"get_current config for plugin {self.__class__.__name__}")
            return self._config.get_current(secrets_is_allowed)

    @hookimpl
    def get_schema(self, schema_type: SchemaTypes = "default"):
        if self._config:
            logger.info(f"get_current config for plugin {self.__class__.__name__}")
            return self._config.get_schema(schema_type)

    # @hookimpl
    # def reset(self):
    #     if self._config:
    #         self._config.reset_defaults()
    #         logger.info(f"reset config to defaults for plugin {self.__class__.__name__}")
