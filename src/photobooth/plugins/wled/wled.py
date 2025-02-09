import logging

from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import WledConfig

logger = logging.getLogger(__name__)


class Wled(BasePlugin[WledConfig]):
    def __init__(self):
        super().__init__()

        self._config: WledConfig = WledConfig()

    @hookimpl
    def start(self):
        pass

    @hookimpl
    def stop(self):
        pass
