import logging

from photobooth.services.config.baseconfig import BaseConfig

logger = logging.getLogger(__name__)


class BasePlugin:
    def __init__(self):
        self._config: BaseConfig = None
