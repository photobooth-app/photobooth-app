"""Base service and resources module."""

import logging
from enum import Enum, auto

import pymitter

from ..appconfig import AppConfig


class EnumStatus(Enum):
    """enum for status"""

    uninitialized = auto()
    initialized = auto()
    started = auto()
    stopped = auto()
    active = auto()
    fault = auto()
    disabled = auto()


class BaseService:
    """All services (factory/singleton) and resources derive from this base class
    logger and eventbus are set here
    """

    _status = EnumStatus.uninitialized

    def __init__(self, evtbus: pymitter.EventEmitter, config: AppConfig) -> None:
        self._logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}",
        )

        self._evtbus = evtbus
        self._config = config

        self.set_status_initialized()

    def set_status_initialized(self):
        self._set_status(EnumStatus.initialized)

    def set_status_started(self):
        self._set_status(EnumStatus.started)

    def set_status_stopped(self):
        self._set_status(EnumStatus.stopped)

    def set_status_active(self):
        self._set_status(EnumStatus.active)

    def set_status_fault(self):
        self._set_status(EnumStatus.fault)

    def get_status(self) -> EnumStatus:
        return self._status

    def _set_status(self, new_status: EnumStatus):
        self._status = new_status
