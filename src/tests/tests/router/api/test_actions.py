import logging
from collections.abc import Generator
from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container
from photobooth.services.processing import ProcessingService
from photobooth.utils.exceptions import ProcessMachineOccupiedError

logger = logging.getLogger(name=None)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        yield client
        container.stop()


def test_chose_1pic(client: TestClient):
    with patch.object(container.processing_service, "trigger_action") as mock:
        # emulate action
        response = client.get("/actions/image/0")
        assert response.status_code == 200

        mock.assert_called()


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


def test_chose_collage(client: TestClient):
    with patch.object(container.processing_service, "trigger_action") as mock:
        # emulate action
        response = client.get("/actions/collage/0")
        assert response.status_code == 200

        mock.assert_called()


def test_chose_animation(client: TestClient):
    with patch.object(container.processing_service, "trigger_action") as mock:
        # emulate action
        response = client.get("/actions/animation/0")
        assert response.status_code == 200

        mock.assert_called()


def test_chose_video(client: TestClient):
    with patch.object(container.processing_service, "trigger_action") as mock:
        # emulate action
        response = client.get("/actions/video/0")
        assert response.status_code == 200

        mock.assert_called()


def test_chose_multicamera(client: TestClient):
    with patch.object(container.processing_service, "trigger_action") as mock:
        # emulate action
        response = client.get("/actions/multicamera/0")
        assert response.status_code == 200

        mock.assert_called()
