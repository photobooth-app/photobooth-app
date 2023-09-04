import logging

import pytest
from fastapi.testclient import TestClient
from httpx_sse import connect_sse

from photobooth.application import app

logger = logging.getLogger(name=None)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:

        # explicit start the informationservice as there is no autostart
        client.app.container.services.information_service.init()

        yield client
        client.app.container.shutdown_resources()


def test_sse_stream(client: TestClient):
    messages_counter = 0
    information_counter = 0
    ping_counter = 0

    with connect_sse(client, "GET", "http://test/sse") as event_source:
        for sse in event_source.iter_sse():
            if sse.event == "message":
                messages_counter += 1
            if sse.event == "information":
                information_counter += 1
            if sse.event == "ping":
                ping_counter += 1

            logger.debug(f"{sse.event=}, {sse.data=}, {sse.id=}, {sse.retry=}")

    logger.info(f"seen {messages_counter} messages, {information_counter} information and {ping_counter} pings")

    assert messages_counter > 0
    assert information_counter > 0
    assert ping_counter > 0

