from unittest import mock
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container
from photobooth.database.schemas import MediaitemPublic
from photobooth.services.mediacollectionservice import MediacollectionService


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        yield client
        container.stop()


def test_get_items(client: TestClient):
    response = client.get("/mediacollection/")

    assert response.status_code == 200
    MediaitemPublic.model_validate(response.json()[0])


def test_get_items_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(MediacollectionService, "db_get_images", error_mock):
        response = client.get("/mediacollection/")
        assert response.status_code == 500
        assert "detail" in response.json()


def test_get_item(client: TestClient):
    mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()
    response = client.get(f"/mediacollection/{mediaitem.id}")

    assert response.status_code == 200
    assert MediaitemPublic.model_validate(response.json()) == MediaitemPublic.model_validate(mediaitem)


def test_get_item_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(MediacollectionService, "db_get_image_by_id", error_mock):
        mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()
        response = client.get(f"/mediacollection/{mediaitem.id}")
        assert response.status_code == 500
        assert "detail" in response.json()


@patch("os.remove")
def test_delete_item(mock_remove, client: TestClient):
    mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()

    response = client.delete(f"/mediacollection/{mediaitem.id}")

    assert response.is_success

    # check os.remove was invoked
    mock_remove.assert_called()


def test_delete_item_exception_nonexistant(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(MediacollectionService, "delete_image_by_id", error_mock):
        response = client.delete(f"/mediacollection/{uuid4()}")  # generated id is non-existant!
        assert response.status_code == 500
        assert "detail" in response.json()


@patch("os.remove")
def test_delete_items(mock_remove, client: TestClient):
    response = client.delete("/mediacollection/")

    assert response.is_success

    # check os.remove was invoked
    mock_remove.assert_called()


def test_delete_items_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(MediacollectionService, "delete_all_mediaitems", error_mock):
        response = client.delete("/mediacollection/")
        assert response.status_code == 500
        assert "detail" in response.json()
