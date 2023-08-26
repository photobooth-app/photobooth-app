import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from photobooth.application import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        yield client
        client.app.container.shutdown_resources()


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


def test_invalid_modechange(client: TestClient):
    response = client.get("/aquisition/mode/invalidmode")
    assert response.status_code == 500
