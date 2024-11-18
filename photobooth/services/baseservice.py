"""Base service and resources module."""

import logging
from enum import Enum

from .sseservice import SseService


class EnumStatus(Enum):
    """enum for status"""

    uninitialized = 10
    initialized = 11
    disabled = 12
    faulty = 13

    stopped = 21
    stopping = 22

    starting = 30

    started = 40


class BaseService:
    """All services (factory/singleton) and resources derive from this base class
    logger and eventbus are set here
    """

    def __init__(self, sse_service: SseService) -> None:
        self._status: EnumStatus = EnumStatus.uninitialized
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._sse_service = sse_service

        self._set_status(EnumStatus.initialized)

    def disabled(self):
        self._set_status(EnumStatus.disabled)

    def start(self):
        self._set_status(EnumStatus.starting)

    def stop(self):
        self._set_status(EnumStatus.stopping)

    def started(self):
        self._set_status(EnumStatus.started)

    def stopped(self):
        self._set_status(EnumStatus.stopped)

    def faulty(self):
        self._set_status(EnumStatus.faulty)

    def is_running(self):
        return True if self._status.value >= EnumStatus.started.value else False

    def get_status(self) -> EnumStatus:
        return self._status

    def _set_status(self, new_status: EnumStatus):
        self._status = new_status
        self._logger.info(f"service {self.__class__.__name__} now {self._status}")
