import logging
from collections.abc import Generator
from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container
from photobooth.services.processing import ProcessingService

logger = logging.getLogger(name=None)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        yield client
        container.stop()


def test_chose_video_stoprecording(client: TestClient):
    with patch.object(container.processing_service, "queue_external_event") as mock:
        # emulate action
        response = client.get("/processing/next")
        assert response.status_code == 200

        mock.assert_called_with("next")


def test_confirm_reject_abort(client: TestClient):
    with patch.object(container.processing_service, "continue_process") as mock:
        # emulate action
        response = client.get("/processing/confirm")
        assert response.status_code == 200

        mock.assert_called()

    with patch.object(container.processing_service, "reject_capture") as mock:
        # emulate action
        response = client.get("/processing/reject")
        assert response.status_code == 200

        mock.assert_called()

    with patch.object(container.processing_service, "abort_process") as mock:
        # emulate action
        response = client.get("/processing/abort")
        assert response.status_code == 200

        mock.assert_called()


def test_confirm_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(ProcessingService, "continue_process", error_mock):
        response = client.get("/processing/confirm")
        assert response.status_code == 500
        assert "detail" in response.json()


def test_reject_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(ProcessingService, "reject_capture", error_mock):
        response = client.get("/processing/reject")
        assert response.status_code == 500
        assert "detail" in response.json()


def test_abort_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(ProcessingService, "abort_process", error_mock):
        response = client.get("/processing/abort")
        assert response.status_code == 500
        assert "detail" in response.json()
