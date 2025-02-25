import logging
from typing import Generic, TypeVar

from photobooth.services.config.baseconfig import BaseConfig

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseConfig)


class BasePlugin(Generic[T]):
    def __init__(self):
        self._config: T


class BaseFilter(BasePlugin[T]):
    def __init__(self):
        super().__init__()

    def unify(self, ambigous_filter: str):
        return f"{type(self).__name__}.{ambigous_filter}"

    def deunify(self, unique_filter: str):
        (name, filt) = str(unique_filter).split(".", 2)
        if name == type(self).__name__:
            return filt
        else:
            return None
