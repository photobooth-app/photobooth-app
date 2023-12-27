from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.services.config import AppConfig, appconfig
from photobooth.services.processingservice import ProcessingService
from photobooth.utils.exceptions import ProcessMachineOccupiedError

appconfig.__dict__.update(AppConfig())


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        yield client
        client.app.container.shutdown_resources()


def test_chose_1pic(client: TestClient):
    response = client.get("/processing/chose/1pic")
    assert response.status_code == 200


def test_chose_1pic_occupied(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = ProcessMachineOccupiedError("mock error")

    with patch.object(ProcessingService, "start_job_1pic", error_mock):
        response = client.get("/processing/chose/1pic")
        assert response.status_code == 400


def test_chose_1pic_otherexception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(ProcessingService, "start_job_1pic", error_mock):
        response = client.get("/processing/chose/1pic")
        assert response.status_code == 500


def test_confirm_reject_abort_in_idle(client: TestClient):
    # statemachine in idle
    response = client.get("/processing/cmd/confirm")
    assert response.status_code == 500
    response = client.get("/processing/cmd/reject")
    assert response.status_code == 500
    response = client.get("/processing/cmd/abort")
    assert response.status_code == 200


def test_confirm_reject_in_collage(client: TestClient):
    appconfig.common.collage_automatic_capture_continue = False

    # statemachine in idle
    response = client.get("/processing/chose/collage")
    assert response.status_code == 200  # one captured
    response = client.get("/processing/cmd/confirm")
    assert response.status_code == 200  # confirmed, done, because 1 capture in collage default only

    # statemachine in idle
    response = client.get("/processing/chose/collage")
    assert response.status_code == 200  # one captured
    response = client.get("/processing/cmd/reject")
    assert response.status_code == 200  # rejected, next is captured now
    response = client.get("/processing/cmd/reject")
    assert response.status_code == 200  # rejected, next is captured now
    response = client.get("/processing/cmd/confirm")
    assert response.status_code == 200  # confirmed, done, because 1 capture in collage default only

    # statemachine in idle
    response = client.get("/processing/chose/collage")
    assert response.status_code == 200  # one captured
    response = client.get("/processing/cmd/reject")
    assert response.status_code == 200  # rejected, next is captured now
    response = client.get("/processing/cmd/abort")
    assert response.status_code == 200  # still not satisfied, abort


def test_chose_collage(client: TestClient):
    # default config: config.common.collage_automatic_capture_continue = True
    response = client.get("/processing/chose/collage")
    assert response.status_code == 200


def test_chose_1pic_with_capturemode(client: TestClient):
    response = client.get("/aquisition/mode/capture")
    assert response.status_code == 202

    response = client.get("/aquisition/still")
    assert response.status_code == 200
