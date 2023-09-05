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
from typing import Any

from fastapi import APIRouter, Request
from pymitter import EventEmitter
from sse_starlette import ServerSentEvent

from ..appconfig import AppConfig
from .baseservice import BaseService
from .mediacollection.mediaitem import MediaItem

logger = logging.getLogger(__name__)


@dataclass
class SseEventBase:
    """basic class for sse events"""

    # event: str = None
    # data: str = None


@dataclass
class SseEventFrontendNotification(SseEventBase):
    """some visible message in frontend"""

    # TODO: implement in frontend
    type: str = None  # could be enum green, yellow, red...
    message: str = ""

    @property
    def data(self) -> str:
        return json.dumps(
            dict(
                type=self.type,
                message=self.message,
            )
        )


@dataclass
class SseEventProcessStateinfo(SseEventBase):
    """_summary_"""

    countdown: float
    display_cheese: bool  # TODO: implement in frontend
    state: str

    event: str = "ProcessStateinfo"

    @property
    def data(self) -> str:
        return json.dumps(
            dict(
                state=self.state,
                countdown=self.countdown,
                display_cheese=self.display_cheese,
            )
        )


@dataclass
class SseEventDbInit(SseEventBase):
    """send the complete database"""

    event: str = "DbInit"
    mediaitems: list[MediaItem] = None

    @property
    def data(self) -> str:
        return json.dumps([item.asdict() for item in self.mediaitems])


@dataclass
class SseEventDbInsert(SseEventBase):
    """basic class for sse events"""

    event: str = "DbInsert"
    mediaitem: MediaItem = None
    # present:bool=False # maybe not needed.

    @property
    def data(self) -> str:
        return json.dumps(self.mediaitem.asdict())


@dataclass
class SseEventDbRemove(SseEventBase):
    """basic class for sse events"""

    event: str = "DbRemove"
    mediaitem: MediaItem = None

    @property
    def data(self) -> str:
        return json.dumps(self.mediaitem.asdict())


@dataclass
class SseEventLogRecord(SseEventBase):
    """basic class for sse events"""

    time: str = None
    level: str = None
    message: str = None
    name: str = None
    funcName: str = None
    lineno: str = None

    event: str = "logrecord"

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
            )
        )


@dataclass
class SseEventInformationRecord(SseEventBase):
    """basic class for sse events"""

    event: str = "informationrecord"

    cpu1_5_15: list[float] = None
    active_threads: int = None
    memory: dict[str, Any] = None
    cma: dict[str, Any] = None
    disk: dict[str, Any] = None

    @property
    def data(self) -> str:
        return json.dumps(
            dict(
                cpu1_5_15=self.cpu1_5_15,
                active_threads=self.active_threads,
                memory=self.memory,
                cma=self.cma,
                disk=self.disk,
            )
        )


@dataclass
class Client:
    """Class each individual client connected"""

    request: Request = None
    queue: Queue = Queue(100)


class SseService(BaseService):
    def __init__(self, evtbus: EventEmitter, config: AppConfig):
        super().__init__(evtbus, config)

        # keep track of client connections with each individual request and queue.
        self._clients: [Client] = []

        # listener services use to send messages to connected clients.
        self._evtbus.on("sse_dispatch_new", self.dispatch_event)

    def setup_client(self, client):
        self._clients.append(client)
        logger.info(f"SSE subscription added for client {client.request.client}")
        logger.debug(f"SSE clients listed {[_client.request for _client in self._clients]}")

        # TODO: get first information here?
        # or keep evtemitter?
        # or call function in other classes
        # or send event via dependency injection framework? (is this possible?)

    def remove_client(self, client):
        logger.debug(f"SSE subscription remove for {client.request.client} requested")

        # iterate over client list and remove.
        for index, _client in enumerate(self._clients):
            if _client.request is client.request:
                removed_client = self._clients.pop(index)
                logger.debug(f"SSE subscription removed for {removed_client}")
                break

        if not removed_client:
            logger.warning("the client was not found in the list, continue")

        logger.debug(f"SSE clients listed {[_client.request for _client in self._clients]}")

    def dispatch_event(self, sse_event_data: SseEventBase):
        try:
            for client in self._clients:
                client.queue.put_nowait(
                    ServerSentEvent(
                        id=uuid.uuid4(),
                        event=sse_event_data.event,
                        data=sse_event_data.data,
                        retry=10000,
                    )
                )

        except QueueFull:
            # actually never run, because queue size is infinite currently
            pass
        # except Exception as exc:
        #    logger.error(f"error while queue item: {exc}")

    # def add_queue_deprecated_via_evtbus(self, sse_event, sse_data):
    #     logger.warning("using old method!")
    #     try:
    #         for client in self._clients:
    #             client.queue.put_nowait(ServerSentEvent(id=uuid.uuid4(), event=sse_event, data=sse_data, retry=10000))

    #     except QueueFull:
    #         # actually never run, because queue size is infinite currently
    #         pass
    #     except Exception as exc:
    #         logger.error(f"error while queue item: {exc}")

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
                    break

                try:
                    # event = await self._queue.get()
                    event = await asyncio.wait_for(client.queue.get(), timeout=0.5)
                except asyncio.exceptions.TimeoutError:
                    # continue on timeouterror ignore silently. used to abort while loop for testing
                    continue

                # send data to client
                yield event

        except asyncio.CancelledError:
            self.remove_client(client)
            logger.info(f"Disconnected from client {client.request.client}")
