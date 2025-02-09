from collections.abc import Generator
from unittest import mock
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container
from photobooth.services.collection import MediacollectionService


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/") as client:
        container.start()
        yield client
        container.stop()


def test_get_404_missing_item(client: TestClient):
    response = client.get(f"/media/full/{uuid4()}")
    assert response.status_code == 404


def test_get_500_on_fail(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(MediacollectionService, "get_item", error_mock):
        response = client.get(f"/media/full/{uuid4()}")
        assert response.status_code == 500
        assert "detail" in response.json()


def test_get_item_variants(client: TestClient):
    mediaitem = container.mediacollection_service.get_item_latest()

    response = client.get(f"/media/full/{mediaitem.id}")
    assert response.is_success
    assert response.headers.get("content-type", None) is not None
    assert len(response.content) > 512  # check result is more than 512b which is true always

    response = client.get(f"/media/preview/{mediaitem.id}")
    assert response.is_success
    assert response.headers.get("content-type", None) is not None
    assert len(response.content) > 512  # check result is more than 512b which is true always

    response = client.get(f"/media/thumbnail/{mediaitem.id}")
    assert response.is_success
    assert response.headers.get("content-type", None) is not None
    assert len(response.content) > 512  # check result is more than 512b which is true always
