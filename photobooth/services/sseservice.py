"""
_summary_
"""

import asyncio
import json
import logging
import os
import time
import uuid
from asyncio import Queue, QueueFull
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request
from sse_starlette.event import ServerSentEvent

from ..database.models import V3MediaitemPublic
from .jobmodels.base import JobModelBase

logger = logging.getLogger(__name__)


@dataclass
class SseEventBase:
    """basic class for sse events"""

    # event: str = None
    # data: str = None


@dataclass
class SseEventFrontendNotification(SseEventBase):
    """some visible message in frontend"""

    caption: str = ""
    message: str = ""
    color: str = None  # could a color or "positive", "negative", "warning", "info" or None, the UI default
    icon: str = None  # could a quasar icon or None, the UI default
    spinner: str = None  # could be True or False, None same as False

    event: str = "FrontendNotification"

    @property
    def data(self) -> str:
        return json.dumps(
            dict(
                caption=self.caption,
                message=self.message,
                color=self.color,
                icon=self.icon,
                spinner=self.spinner,
            )
        )


@dataclass
class SseEventProcessStateinfo(SseEventBase):
    """_summary_"""

    jobmodel: JobModelBase = None

    event: str = "ProcessStateinfo"

    @property
    def data(self) -> str:
        # logger.debug(self.jobmodel.export()
        if self.jobmodel:
            return json.dumps(self.jobmodel.export())
        else:
            return json.dumps({})


@dataclass
class SseEventDbInsert(SseEventBase):
    """basic class for sse events"""

    event: str = "DbInsert"
    mediaitem: V3MediaitemPublic = None

    @property
    def data(self) -> str:
        return self.mediaitem.model_dump_json()


@dataclass
class SseEventDbRemove(SseEventBase):
    """basic class for sse events"""

    event: str = "DbRemove"
    mediaitem: V3MediaitemPublic = None

    @property
    def data(self) -> str:
        return self.mediaitem.model_dump_json()


@dataclass
class SseEventLogRecord(SseEventBase):
    """basic class for sse events"""

    time: str = None
    level: str = None
    message: str = None
    name: str = None
    funcName: str = None
    lineno: str = None
    # display_notification: bool = None

    event: str = "LogRecord"

    @property
    def data(self) -> str:
        return json.dumps(
            dict(
                time=self.time,
                level=self.level,
                message=self.message,
                name=self.name,
                funcName=self.funcName,
                lineno=self.lineno,
                # display_notification=self.display_notification,
            )
        )


@dataclass
class SseEventOnetimeInformationRecord(SseEventBase):
    """basic class for sse events"""

    event: str = "InformationRecord"

    version: str = None
    platform_system: str = None
    platform_release: str = None
    platform_machine: str = None
    platform_python_version: str = None
    platform_node: str = None
    platform_cpu_count: int = None
    model: str = None
    data_directory: Path = None
    python_executable: str = None
    disk: dict[str, Any] = None

    @property
    def data(self) -> str:
        return json.dumps(
            dict(
                version=self.version,
                platform_system=self.platform_system,
                platform_release=self.platform_release,
                platform_machine=self.platform_machine,
                platform_python_version=self.platform_python_version,
                platform_node=self.platform_node,
                platform_cpu_count=self.platform_cpu_count,
                model=self.model,
                data_directory=str(self.data_directory),
                python_executable=self.python_executable,
                disk=self.disk,
            )
        )


@dataclass
class SseEventIntervalInformationRecord(SseEventBase):
    """basic class for sse events"""

    event: str = "InformationRecord"

    cpu1_5_15: list[float] = None
    memory: dict[str, Any] = None
    cma: dict[str, Any] = None
    backends: dict[str, dict[str, Any]] = None
    printer: dict[str, Any] = None
    stats_counter: dict[str, Any] = None
    limits_counter: dict[str, Any] = None
    battery_percent: int = None
    temperatures: dict[str, Any] = None

    @property
    def data(self) -> str:
        return json.dumps(
            dict(
                cpu1_5_15=self.cpu1_5_15,
                memory=self.memory,
                cma=self.cma,
                backends=self.backends,
                printer=self.printer,
                stats_counter=self.stats_counter,
                limits_counter=self.limits_counter,
                battery_percent=self.battery_percent,
                temperatures=self.temperatures,
            )
        )


@dataclass
class Client:
    """Class each individual client connected"""

    request: Request = None
    queue: Queue = None


class SseService:
    def __init__(self):
        # keep track of client connections with each individual request and queue.
        self._clients: list[Client] = []

    def setup_client(self, client: Client):
        self._clients.append(client)
        logger.info(f"SSE subscription added for client {client.request.client}")
        logger.debug(f"SSE clients listed {[_client.request for _client in self._clients]}")
        # print(f"client.queue {[client.queue for client in self._clients]}")
        # print(f"qsize {[client.queue.qsize() for client in self._clients]}")

    def remove_client(self, client: Client):
        logger.debug(f"SSE subscription remove for {client.request.client} requested")

        # iterate over client list and remove.
        for index, _client in enumerate(self._clients):
            if _client.request is client.request:
                removed_client = self._clients.pop(index)
                logger.debug(f"SSE subscription removed for {removed_client.request.client}")
                break

        if not removed_client:
            logger.warning("the client was not found in the list, continue")

        logger.debug(f"SSE clients listed {[_client.request for _client in self._clients]}")

    def dispatch_event(self, sse_event_data: SseEventBase):
        for client in self._clients:
            try:
                client.queue.put_nowait(
                    ServerSentEvent(
                        id=str(uuid.uuid4()),
                        event=sse_event_data.event,
                        data=sse_event_data.data,
                        retry=10000,
                    )
                )

            except QueueFull:
                # fail in silence if queue is full - though is critical for init sse messages.
                # on the other side, queue better not infinite if disconnect is not working proper and queue remains getting larger
                pass

    async def event_iterator(self, client: Client, timeout=0.0):
        if "PYTEST_CURRENT_TEST" in os.environ:
            # FIXME: workaround for testing until testing with mocks/patching works well...
            timeout = 3.5
            logger.info(f"event_iterator {timeout=} set. positive values used for testing only")

        try:
            starting_time = time.time()
            while not timeout or (time.time() - starting_time < timeout):
                if await client.request.is_disconnected():
                    self.remove_client(client)
                    logger.info(f"client request disconnect, client {client.request.client}")
                    return

                try:
                    yield await asyncio.wait_for(client.queue.get(), timeout=0.5)
                except asyncio.exceptions.TimeoutError:
                    # continue on timeouterror ignore silently. used to abort while loop for testing
                    continue

        except asyncio.CancelledError as exc:
            self.remove_client(client)
            logger.info(f"Disconnected from client {client.request.client}")

            # https://stackoverflow.com/a/53724990
            raise exc
