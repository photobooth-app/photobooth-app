import logging
from typing import Generic, TypeVar

from photobooth.services.config.baseconfig import BaseConfig

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseConfig)


class BasePlugin(Generic[T]):
    def __init__(self):
        self._config: T
