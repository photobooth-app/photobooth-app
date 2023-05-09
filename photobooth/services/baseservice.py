"""Base service and resources module."""

import logging

import pymitter

from ..appconfig import AppConfig


class BaseService:
    """All services (factory/singleton) and resources derive from this base class
    logger and eventbus are set here
    """

    def __init__(self, evtbus: pymitter.EventEmitter, config: AppConfig) -> None:
        self._logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}",
        )

        self._evtbus = evtbus
        self._config = config
