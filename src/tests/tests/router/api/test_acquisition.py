import asyncio
import io
import logging
import time
from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from photobooth.appconfig import appconfig
from photobooth.services.acquisition import AcquisitionService
from photobooth.utils.exceptions import BackendNotRunning

logger = logging.getLogger(name=None)
DUMMY_JPEG = b"\xff\xd8" + b"\x00" * 200 + b"\xff\xd9"


def capture(client: TestClient):
    response = client.get("/aquisition/still")
    try:
        with Image.open(io.BytesIO(response.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc

    assert response.status_code == 200


def test_aquire_still_capturemode(client: TestClient):
    response = client.get("/aquisition/mode/0/capture")
    assert response.status_code == 202

    response = client.get("/aquisition/still")
    assert response.status_code == 200


def test_aquire_still_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(AcquisitionService, "wait_for_still_file", error_mock):
        response = client.get("/aquisition/still")
        assert response.status_code == 500
        assert "detail" in response.json()


def test_aquire_multiple_withmodechange(client: TestClient):
    for _i in range(4):
        response = client.get("/aquisition/mode/0/capture")
        assert response.status_code == 202

        # virtual countdown
        time.sleep(0.2)

        capture(client)

        response = client.get("/aquisition/mode/0/video")
        assert response.status_code == 202


def test_aquire_multiple_nomodechange(client: TestClient):
    for _i in range(0, 4):
        capture(client)


def test_invalid_test_all_modes(client: TestClient):
    response = client.get("/aquisition/mode/0/capture")
    assert response.is_success
    response = client.get("/aquisition/mode/0/video")
    assert response.is_success
    response = client.get("/aquisition/mode/0/standby")
    assert response.is_success


def test_invalid_modechange(client: TestClient):
    response = client.get("/aquisition/mode/0/invalidmode")
    assert response.status_code == 422


@patch(
    "photobooth.services.acquisition.AcquisitionService.wait_for_lores_image",
    side_effect=[DUMMY_JPEG, BackendNotRunning("simulate backend stop")],
)
def test_mjpeg_stream(mock_gen_stream, client: TestClient):
    response = client.get("/aquisition/stream.mjpg")
    assert response.status_code == 200

    # The response is multipart, so content will include headers + JPEG
    body = response.content
    # Extract JPEG markers
    start = body.find(b"\xff\xd8")
    end = body.find(b"\xff\xd9", start) + 2
    frame = body[start:end]

    assert frame.startswith(b"\xff\xd8")
    assert frame.endswith(b"\xff\xd9")
    assert len(frame) > 100


@pytest.mark.asyncio
@patch(
    "photobooth.services.acquisition.AcquisitionService.wait_for_lores_image",
    side_effect=[DUMMY_JPEG],
)
async def test_websocket_stream_stall_if_no_ready_from_client(mock_gen_stream, client: TestClient):

    with client.websocket_connect("ws://test/api/aquisition/stream") as websocket:
        # if there is no "ready" sent from client, it will not deliver a frame and receivebytes should timeout

        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.to_thread(websocket.receive_bytes), timeout=2)


@patch(
    "photobooth.services.acquisition.AcquisitionService.wait_for_lores_image",
    side_effect=[DUMMY_JPEG, BackendNotRunning("simulate backend stop")],
)
def test_websocket_stream(mock_gen_stream, client: TestClient):

    with client.websocket_connect("ws://test/api/aquisition/stream") as websocket:
        # Receive one frame

        websocket.send_text("ready")

        frame = websocket.receive_bytes()
        assert frame.startswith(b"\xff\xd8")
        assert frame.endswith(b"\xff\xd9")
        assert len(frame) > 100


def test_stream_exception_disabled(client: TestClient):
    # disable livestream
    appconfig.backends.enable_livestream = False

    # shall result in error 405
    response = client.get("/aquisition/stream.mjpg")
    assert response.status_code == 405
    assert "detail" in response.json()


def test_capture_multicamera(client: TestClient):
    response = client.get("/aquisition/multicam")
    assert response.status_code == 200

    files: list[str] = response.json()

    for file in files:
        with Image.open(file) as img:
            img.verify()

        response_download = client.get(f"/aquisition/multicam/{file}")
        assert response_download.status_code == 200
        with Image.open(io.BytesIO(response_download.content)) as img:
            img.verify()
