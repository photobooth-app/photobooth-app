import io
import logging
import time
from collections.abc import Generator
from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from photobooth.appconfig import appconfig
from photobooth.application import app
from photobooth.container import container
from photobooth.services.aquisition import AquisitionService

logger = logging.getLogger(name=None)


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


def test_stream(client: TestClient):
    """test not avail yet"""
    pass


def test_stream_exception_disabled(client: TestClient):
    # disable livestream
    appconfig.backends.enable_livestream = False

    # shall result in error 405
    response = client.get("/aquisition/stream.mjpg")
    assert response.status_code == 405
    assert "detail" in response.json()
