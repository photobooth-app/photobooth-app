import logging

from fastapi.testclient import TestClient

from photobooth.container import container

logger = logging.getLogger(name=None)


def test_sse_stream1(client: TestClient):
    processstateinfo_counter = 0
    logrecord_counter = 0
    onetimeinformationrecord_counter = 0
    intervalinformationrecord_counter = 0
    ping_counter = 0

    # start a job so there will be some Process StateInfo
    container.processing_service.trigger_action("image", 0)

    # with httpx2.Client(transport=SSETransport()) as client:
    with client.stream("GET", "/sse") as response:
        for line in response.iter_lines():
            # logger.warning(line)
            if line.startswith("event:"):
                event = line[len("event:") :].lstrip()

                if event == "ProcessStateinfo":
                    processstateinfo_counter += 1
                if event == "LogRecord":
                    logrecord_counter += 1
                if event == "OnetimeInformationRecord":
                    onetimeinformationrecord_counter += 1
                if event == "IntervalInformationRecord":
                    intervalinformationrecord_counter += 1
                if event == "ping":
                    ping_counter += 1

    logger.info(
        f"seen {processstateinfo_counter} processstateinfos, {logrecord_counter} logrecords, "
        f"{intervalinformationrecord_counter} interval-informations {onetimeinformationrecord_counter} onetime-informations and {ping_counter} pings"
    )

    assert processstateinfo_counter > 0
    assert logrecord_counter > 0
    assert onetimeinformationrecord_counter > 0
    assert intervalinformationrecord_counter > 0
    assert ping_counter > 0
