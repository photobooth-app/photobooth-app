import io
import logging
from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import photobooth.routers.api.mediaprocessing
from photobooth.application import app
from photobooth.container import container

from .utils import is_same

logger = logging.getLogger(name=None)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        # need an image for sure as last item because this is safe to filter
        container.processing_service.trigger_action("image", 0)
        container.processing_service.wait_until_job_finished()
        yield client
        container.stop()


def test_preview_filter_original(client: TestClient):
    # get the newest mediaitem
    mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()

    response = client.get(f"/mediaprocessing/preview/{mediaitem.id}/original")

    assert response.status_code == 200

    try:
        with Image.open(io.BytesIO(response.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"preview filter did not return valid image bytes, {exc}") from exc


def test_preview_filter_1977(client: TestClient):
    # get the newest mediaitem
    mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()

    response = client.get(f"/mediaprocessing/preview/{mediaitem.id}/_1977")

    assert response.status_code == 200

    try:
        with Image.open(io.BytesIO(response.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"preview filter did not return valid image bytes, {exc}") from exc


def test_preview_filter_nonexistentitem(client: TestClient):
    response = client.get("/mediaprocessing/preview/nonexistantmediaitem/theresnofilterlikethis")

    assert response.status_code == 404


def test_preview_otherexception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()

    with patch.object(photobooth.routers.api.mediaprocessing, "get_filter_preview", error_mock):
        response = client.get(f"/mediaprocessing/preview/{mediaitem.id}/original")

    assert response.status_code == 500


def test_preview_filter_nonexistentfilter(client: TestClient):
    # get the newest mediaitem
    mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()

    response = client.get(f"/mediaprocessing/preview/{mediaitem.id}/theresnofilterlikethis")

    assert response.status_code == 406


def test_apply_filter_nonexistentfilter(client: TestClient):
    # get the newest mediaitem
    mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()

    response = client.get(f"/mediaprocessing/applyfilter/{mediaitem.id}/theresnofilterlikethis")

    assert response.status_code == 406


def test_apply_filter(client: TestClient):
    # get the newest mediaitem
    mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()

    image_before = Image.open(mediaitem.path_full)
    image_before.load()  # force load (open is lazy!)

    response = client.get(f"/mediaprocessing/applyfilter/{mediaitem.id}/_1977")

    assert response.status_code == 200

    if is_same(image_before, Image.open(mediaitem.path_full)):
        raise AssertionError("img data before and after same. filter was not applied!")


def test_apply_filter_original(client: TestClient):
    # get the newest mediaitem
    mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()

    response = client.get(f"/mediaprocessing/applyfilter/{mediaitem.id}/original")
    assert response.status_code == 200

    image_original = Image.open(mediaitem.path_preview)
    image_original.load()  # force load (open is lazy!)

    response = client.get(f"/mediaprocessing/applyfilter/{mediaitem.id}/_1977")
    assert response.status_code == 200
    if is_same(image_original, Image.open(mediaitem.path_preview)):
        raise AssertionError("img data before and after same. filter was not applied!")

    response = client.get(f"/mediaprocessing/applyfilter/{mediaitem.id}/original")

    assert response.status_code == 200

    assert is_same(image_original, Image.open(mediaitem.path_preview))
