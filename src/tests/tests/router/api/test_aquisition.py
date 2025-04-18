import io
import logging
import time
from collections.abc import Generator
from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from httpx import Auth, Request
from PIL import Image

from photobooth.appconfig import appconfig
from photobooth.application import app
from photobooth.container import container
from photobooth.services.aquisition import AquisitionService

logger = logging.getLogger(name=None)


class NoAuth(Auth):
    """fixes stalling when trying to read the stream but the client tries to authenticate first to the indefinite stream"""

    class ObjClose(Request):
        def close(self): ...

    def auth_flow(self, request):
        yield request

    def sync_auth_flow(self, request):
        yield NoAuth.ObjClose("GET", "http://")

    async def async_auth_flow(self, request):
        yield NoAuth.ObjClose("GET", "http://")


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        yield client
        container.stop()


def capture(client: TestClient):
    response = client.get("/aquisition/still")
    try:
        with Image.open(io.BytesIO(response.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc

    assert response.status_code == 200


def test_aquire_still_capturemode(client: TestClient):
    response = client.get("/aquisition/mode/capture")
    assert response.status_code == 202

    response = client.get("/aquisition/still")
    assert response.status_code == 200


def test_aquire_still_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(AquisitionService, "wait_for_still_file", error_mock):
        response = client.get("/aquisition/still")
        assert response.status_code == 500
        assert "detail" in response.json()


def test_aquire_multiple_withmodechange(client: TestClient):
    for _i in range(0, 4):
        response = client.get("/aquisition/mode/capture")
        assert response.status_code == 202

        # virtual countdown
        time.sleep(1)

        capture(client)

        response = client.get("/aquisition/mode/preview")
        assert response.status_code == 202


def test_aquire_multiple_nomodechange(client: TestClient):
    for _i in range(0, 4):
        capture(client)


def test_invalid_test_all_modes(client: TestClient):
    response = client.get("/aquisition/mode/capture")
    assert response.is_success
    response = client.get("/aquisition/mode/preview")
    assert response.is_success
    response = client.get("/aquisition/mode/video")
    assert response.is_success
    response = client.get("/aquisition/mode/idle")
    assert response.is_success


def test_invalid_modechange(client: TestClient):
    response = client.get("/aquisition/mode/invalidmode")
    assert response.status_code == 422


def test_mjpeg_stream(client: TestClient):
    with client.stream("GET", "/aquisition/stream.mjpg", auth=NoAuth()) as response:
        assert response.status_code == 200
        buffer = b""
        jpeg_start = b"\xff\xd8"
        jpeg_end = b"\xff\xd9"

        # Read bytes until one JPEG image is captured
        for chunk in response.iter_bytes():
            buffer += chunk
            if jpeg_start in buffer and jpeg_end in buffer:
                start = buffer.find(jpeg_start)
                end = buffer.find(jpeg_end, start) + 2
                jpeg_data = buffer[start:end]
                # break

                # Now we verify the JPEG
                assert jpeg_data
                assert jpeg_data.startswith(jpeg_start)
                assert jpeg_data.endswith(jpeg_end)
                assert len(jpeg_data) > 100  # Arbitrary minimum size check

                break


def test_stream_exception_disabled(client: TestClient):
    # disable livestream
    appconfig.backends.enable_livestream = False

    # shall result in error 405
    response = client.get("/aquisition/stream.mjpg")
    assert response.status_code == 405
    assert "detail" in response.json()
