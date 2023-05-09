import pytest
from fastapi.testclient import TestClient

from photobooth.application import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        yield client


def test_chose_1pic(client: TestClient):
    response = client.get("/processing/chose/1pic")
    assert response.status_code == 200

    processing_service = client.app.container.services.processing_service()

    processing_service.thrill()

    response = client.get("/processing/chose/1pic")
    assert response.status_code == 400

    processing_service._reset()

    response = client.get("/processing/chose/1pic")
    assert response.status_code == 200


def test_chose_1pic_with_capturemode(client: TestClient):
    response = client.get("/aquisition/mode/capture")
    assert response.status_code == 200

    response = client.get("/aquisition/still")
    assert response.status_code == 200
