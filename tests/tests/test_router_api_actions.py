import logging
from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container
from photobooth.services.processingservice import ProcessingService
from photobooth.utils.exceptions import ProcessMachineOccupiedError

logger = logging.getLogger(name=None)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        yield client
        container.stop()


def test_chose_1pic(client: TestClient):
    with patch.object(container.processing_service, "trigger_action"):
        # emulate action
        response = client.get("/actions/image/0")
        assert response.status_code == 200

        container.processing_service.trigger_action.assert_called()


def test_chose_collage(client: TestClient):
    with patch.object(container.processing_service, "trigger_action"):
        # emulate action
        response = client.get("/actions/collage/0")
        assert response.status_code == 200

        container.processing_service.trigger_action.assert_called()


def test_chose_animation(client: TestClient):
    with patch.object(container.processing_service, "trigger_action"):
        # emulate action
        response = client.get("/actions/animation/0")
        assert response.status_code == 200

        container.processing_service.trigger_action.assert_called()


def test_chose_video(client: TestClient):
    with patch.object(container.processing_service, "trigger_action"):
        # emulate action
        response = client.get("/actions/video/0")
        assert response.status_code == 200

        container.processing_service.trigger_action.assert_called()


def test_chose_video_stoprecording(client: TestClient):
    with patch.object(container.processing_service, "stop_recording"):
        # emulate action
        response = client.get("/actions/stop")
        assert response.status_code == 200

        container.processing_service.stop_recording.assert_called()


def test_chose_1pic_occupied(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = ProcessMachineOccupiedError("mock error")

    with patch.object(ProcessingService, "trigger_action", error_mock):
        response = client.get("/actions/image/0")
        assert response.status_code == 400


def test_chose_1pic_otherexception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(ProcessingService, "trigger_action", error_mock):
        response = client.get("/actions/image/0")
        assert response.status_code == 500


def test_confirm_reject_abort(client: TestClient):
    with patch.object(container.processing_service, "confirm_capture"):
        # emulate action
        response = client.get("/actions/confirm")
        assert response.status_code == 200

        container.processing_service.confirm_capture.assert_called()

    with patch.object(container.processing_service, "reject_capture"):
        # emulate action
        response = client.get("/actions/reject")
        assert response.status_code == 200

        container.processing_service.reject_capture.assert_called()

    with patch.object(container.processing_service, "abort_process"):
        # emulate action
        response = client.get("/actions/abort")
        assert response.status_code == 200

        container.processing_service.abort_process.assert_called()


def test_confirm_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(ProcessingService, "confirm_capture", error_mock):
        response = client.get("/actions/confirm")
        assert response.status_code == 500
        assert "detail" in response.json()


def test_reject_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(ProcessingService, "reject_capture", error_mock):
        response = client.get("/actions/confirm")
        assert response.status_code == 500
        assert "detail" in response.json()


def test_stop_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(ProcessingService, "stop_recording", error_mock):
        response = client.get("/actions/stop")
        assert response.status_code == 500
        assert "detail" in response.json()


def test_abort_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(ProcessingService, "abort_process", error_mock):
        response = client.get("/actions/abort")
        assert response.status_code == 500
        assert "detail" in response.json()
