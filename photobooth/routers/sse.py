import asyncio
import logging
import os
import time
import uuid
from asyncio import Queue, QueueFull
from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request
from pymitter import EventEmitter
from sse_starlette import EventSourceResponse, ServerSentEvent

from ..containers import ApplicationContainer

logger = logging.getLogger(__name__)
sse_router = APIRouter(
    tags=["home"],
)


class StreamClass:
    def __init__(self, evtbus: EventEmitter, queue: Queue):
        self._evtbus = evtbus
        self._queue = queue

    def add_subscriptions(self):
        logger.debug("SSE subscription added")
        self._evtbus.on("publishSSE", self.add_queue)

    def remove_subscriptions(self):
        self._evtbus.off("publishSSE", self.add_queue)
        logger.debug("SSE subscription removed")

    def add_queue(self, sse_event, sse_data):
        try:
            self._queue.put_nowait(
                ServerSentEvent(
                    id=uuid.uuid4(), event=sse_event, data=sse_data, retry=10000
                )
            )
        except QueueFull:
            # actually never run, because queue size is infinite currently
            pass

    async def event_iterator(self, request: Request, timeout=0.0):
        if "PYTEST_CURRENT_TEST" in os.environ:
            # FIXME: workaround for testing until testing with mocks/patching works well...
            timeout = 3.5
        logger.info(
            f"event_iterator {timeout=} set. positive values used for testing only"
        )
        try:
            starting_time = time.time()
            while not timeout or (time.time() - starting_time < timeout):
                if await request.is_disconnected():
                    self.remove_subscriptions()
                    logger.info(f"client request disconnect, client {request.client}")
                    break

                try:
                    # event = await self._queue.get()
                    event = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                except asyncio.exceptions.TimeoutError:
                    # continue on timeouterror ignore silently. used to abort while loop for testing
                    continue

                # send data to client
                yield event

        except asyncio.CancelledError:
            self.remove_subscriptions()
            logger.info(f"Disconnected from client {request.client}")


@sse_router.get("/sse")
@inject
async def subscribe(
    request: Request,
    evtbus: EventEmitter = Depends(Provide[ApplicationContainer.services.evtbus]),
):
    """
    Eventstream to feed clients with server generated events and data
    """

    # local message queue, each client has it's own queue
    # limit max queue size in case client doesnt catch up so fast.
    # if there are more than 100 messages in the queue
    # it can be assumed that the connection is broken or something.
    # Queue changed in python 3.10, for compatiblity subscribe is
    # async since queue reuses the async thread
    # that would not be avail if outer function of queue is sync.
    # https://docs.python.org/3.11/library/asyncio-queue.html

    streamclass = StreamClass(evtbus=evtbus, queue=Queue(100))

    logger.info(f"Client connected {request.client}")
    streamclass.add_subscriptions()

    # initial messages on client connect
    streamclass.add_queue(
        sse_event="message", sse_data=f"Client connected {request.client}"
    )
    logger.info("added init message")

    # all modules can register this event to send initial messages on connection
    await evtbus.emit_async("publishSSE/initial")

    return EventSourceResponse(
        streamclass.event_iterator(request=request),
        ping=1,
        ping_message_factory=lambda: ServerSentEvent(
            datetime.utcnow(), event="ping"
        ).encode(),
    )
