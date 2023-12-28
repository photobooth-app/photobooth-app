import logging
from asyncio import Queue
from datetime import datetime

from dependency_injector.wiring import inject
from fastapi import APIRouter, Request
from sse_starlette import EventSourceResponse, ServerSentEvent

from ..container import container
from ..services.sseservice import Client

logger = logging.getLogger(__name__)
sse_router = APIRouter(
    tags=["home"],
)


@sse_router.get("/sse")
@inject
async def subscribe(request: Request):
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
    client = Client(request, queue)
    container.sse_service.setup_client(client=client)

    # following modules send some data on connection init to client:
    container.information_service.initial_emit()
    container.processing_service.initial_emit()

    return EventSourceResponse(
        container.sse_service.event_iterator(client=client),
        ping=1,
        ping_message_factory=lambda: ServerSentEvent(datetime.utcnow(), event="ping").encode(),
    )
