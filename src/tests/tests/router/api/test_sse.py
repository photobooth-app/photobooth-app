import logging
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from httpx_sse import connect_sse

from photobooth.application import app
from photobooth.container import container

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        yield client
        container.stop()


def test_sse_stream(client: TestClient):
    processstateinfo_counter = 0
    logrecord_counter = 0
    onetimeinformationrecord_counter = 0
    intervalinformationrecord_counter = 0
    ping_counter = 0

    # start a job so there will be some Process StateInfo
    container.processing_service.trigger_action("image", 0)

    with connect_sse(client, "GET", "/sse") as event_source:
        for sse in event_source.iter_sse():
            if sse.event == "ProcessStateinfo":
                processstateinfo_counter += 1
            if sse.event == "LogRecord":
                logrecord_counter += 1
            if sse.event == "OnetimeInformationRecord":
                onetimeinformationrecord_counter += 1
            if sse.event == "IntervalInformationRecord":
                intervalinformationrecord_counter += 1
            if sse.event == "ping":
                ping_counter += 1

            logger.debug(f"{sse.event=}, {sse.data=}, {sse.id=}, {sse.retry=}")

    logger.info(
        f"seen {processstateinfo_counter} processstateinfos, {logrecord_counter} logrecords, "
        f"{intervalinformationrecord_counter} interval-informations {onetimeinformationrecord_counter} onetime-informations and {ping_counter} pings"
    )

    assert processstateinfo_counter > 0
    assert logrecord_counter > 0
    assert onetimeinformationrecord_counter > 0
    assert intervalinformationrecord_counter > 0
    assert ping_counter > 0
