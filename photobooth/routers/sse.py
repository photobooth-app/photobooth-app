import asyncio
import logging
import uuid
from asyncio import Queue, QueueFull

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request
from pymitter import EventEmitter
from sse_starlette import EventSourceResponse, ServerSentEvent

from ..containers import ApplicationContainer

logger = logging.getLogger(__name__)
sse_router = APIRouter(
    tags=["home"],
)


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
    queue = Queue(100)

    def add_subscriptions():
        logger.debug(f"SSE subscription added, client {request.client}")
        evtbus.on("publishSSE", add_queue)

    def remove_subscriptions():
        evtbus.off("publishSSE", add_queue)
        logger.debug(f"SSE subscription removed, client {request.client}")

    def add_queue(sse_event, sse_data):
        try:
            queue.put_nowait(
                ServerSentEvent(
                    id=uuid.uuid4(), event=sse_event, data=sse_data, retry=10000
                )
            )
        except QueueFull as exc:
            # actually never run, because queue size is infinite currently
            remove_subscriptions()
            logger.error(
                f"SSE queue full! event '{sse_event}' not sent. Connection broken?"
            )
            raise HTTPException(
                status_code=500,
                detail=f"SSE queue full! event '{sse_event}' not sent. Connection broken?",
            ) from exc

    async def event_iterator():
        try:
            while True:
                if await request.is_disconnected():
                    remove_subscriptions()
                    logger.info(f"client request disconnect, client {request.client}")
                    break

                event = await queue.get()

                # send data to client
                yield event

        except asyncio.CancelledError:
            remove_subscriptions()
            logger.info(f"Disconnected from client {request.client}")

    logger.info(f"Client connected {request.client}")
    add_subscriptions()

    # initial messages on client connect
    add_queue(sse_event="message", sse_data=f"Client connected {request.client}")

    # all modules can register this event to send initial messages on connection
    await evtbus.emit_async("publishSSE/initial")

    return EventSourceResponse(event_iterator(), ping=1)
