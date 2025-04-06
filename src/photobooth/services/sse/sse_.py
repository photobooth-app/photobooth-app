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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Request
from sse_starlette.event import ServerSentEvent
from statemachine import State

from ...database.schemas import MediaitemPublic
from ..processor.base import JobModelBase

logger = logging.getLogger(__name__)


@dataclass
class SseEventBase:
    """basic class for sse events"""

    # event: str
    # data: str


@dataclass
class SseEventTranslateableFrontendNotification(SseEventBase):
    """some visible message in frontend"""

    message_key: str = ""
    context_data: dict[str, str] = field(default_factory=dict)
    color: str | None = None  # could a color or "positive", "negative", "warning", "info" or None, the UI default
    icon: str | None = None  # could a quasar icon or None, the UI default
    spinner: bool | None = None  # could be True or False, None same as False

    event: str = "TranslateableFrontendNotification"

    @property
    def data(self) -> str:
        return json.dumps(
            dict(
                message_key=self.message_key,
                context_data=self.context_data,
                color=self.color,
                icon=self.icon,
                spinner=self.spinner,
            )
        )


@dataclass
class SseEventProcessStateinfo(SseEventBase):
    """_summary_"""

    source: State
    target: State
    jobmodel: JobModelBase | None

    event: str = "ProcessStateinfo"

    @property
    def data(self) -> str:
        # logger.debug(self.jobmodel.export()
        if self.jobmodel:
            return json.dumps(
                dict(
                    source=self.source.id,
                    target=self.target.id,
                    jobmodel=self.jobmodel.export(),
                )
            )
        else:
            return json.dumps({})


@dataclass
class SseEventDbInsert(SseEventBase):
    mediaitem: MediaitemPublic

    event: str = "DbInsert"

    @property
    def data(self) -> str:
        return self.mediaitem.model_dump_json()


@dataclass
class SseEventDbUpdate(SseEventBase):
    mediaitem: MediaitemPublic

    event: str = "DbUpdate"

    @property
    def data(self) -> str:
        return self.mediaitem.model_dump_json()


@dataclass
class SseEventDbRemove(SseEventBase):
    mediaitem: MediaitemPublic

    event: str = "DbRemove"

    @property
    def data(self) -> str:
        return self.mediaitem.model_dump_json()


@dataclass
class SseEventLogRecord(SseEventBase):
    """basic class for sse events"""

    time: str
    level: str
    message: str
    name: str
    funcName: str
    lineno: str
    # display_notification: bool

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

    version: str
    platform_system: str
    platform_release: str
    platform_machine: str
    platform_python_version: str
    platform_node: str
    platform_cpu_count: int | None
    model: str
    data_directory: Path
    python_executable: str
    disk: dict[str, Any]

    event: str = "InformationRecord"

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

    cpu_percent: float
    memory: dict[str, Any]
    cma: dict[str, Any]
    backends: dict[str, dict[str, Any]]
    stats_counter: list[dict[str, Any]]
    limits_counter: list[dict[str, Any]]
    battery_percent: int | None
    temperatures: dict[str, Any]
    mediacollection: dict[str, Any]

    event: str = "InformationRecord"

    @property
    def data(self) -> str:
        return json.dumps(
            dict(
                cpu_percent=self.cpu_percent,
                memory=self.memory,
                cma=self.cma,
                backends=self.backends,
                stats_counter=self.stats_counter,
                limits_counter=self.limits_counter,
                battery_percent=self.battery_percent,
                temperatures=self.temperatures,
                mediacollection=self.mediacollection,
            )
        )


@dataclass
class Client:
    """Class each individual client connected"""

    request: Request
    queue: Queue


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

        logger.debug(f"SSE clients listed {[_client.request for _client in self._clients]}")

    def dispatch_event(self, sse_event_data):
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
