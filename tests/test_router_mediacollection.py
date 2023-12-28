from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container
from photobooth.services.config import appconfig
from photobooth.services.mediacollectionservice import MediacollectionService


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        container.start()
        container.processing_service.start_job_1pic()
        yield client
        container.stop()


def test_get_items(client: TestClient):
    response = client.get("/mediacollection/getitems")
    assert response.status_code == 200


def test_get_items_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(MediacollectionService, "db_get_images_as_dict", error_mock):
        response = client.get("/mediacollection/getitems")
        assert response.status_code == 500
        assert "detail" in response.json()


@patch("os.remove")
def test_delete_item(mock_remove, client: TestClient):
    mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()

    response = client.get("/mediacollection/delete", params={"image_id": mediaitem.id})

    assert response.status_code == 204

    # check os.remove was invoked
    mock_remove.assert_called()


def test_delete_item_exception_nonexistant(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(MediacollectionService, "delete_image_by_id", error_mock):
        response = client.get("/mediacollection/delete", params={"image_id": "illegalid"})
        assert response.status_code == 500
        assert "detail" in response.json()


@patch("os.remove")
def test_delete_items(mock_remove, client: TestClient):
    response = client.get("/mediacollection/delete_all")

    assert response.status_code == 204

    # check os.remove was invoked
    mock_remove.assert_called()


def test_delete_items_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(MediacollectionService, "delete_images", error_mock):
        response = client.get("/mediacollection/delete_all")
        assert response.status_code == 500
        assert "detail" in response.json()
