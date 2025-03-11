import io
import logging
from collections.abc import Generator
from unittest import mock
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import photobooth.routers.api.filter
import photobooth.services
import photobooth.services.mediaprocessing.steps.image
from photobooth.application import app
from photobooth.container import container

from ...util import is_same

logger = logging.getLogger(name=None)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        # need an image for sure as last item because this is safe to filter
        # container.processing_service.trigger_action("image", 0)
        # container.processing_service.wait_until_job_finished()
        yield client
        container.stop()


def test_get_avail_filter(client: TestClient):
    response = client.get("/filter/")

    assert response.is_success


def test_get_avail_filter_err(client: TestClient):
    # https://docs.python.org/3/library/unittest.mock.html#where-to-patch
    with patch.object(photobooth.routers.api.filter, "get_plugin_userselectable_filters", side_effect=RuntimeError("mock")):
        response = client.get("/filter/")

        assert response.status_code == 500


def test_preview_filter_original(client: TestClient):
    # get the newest mediaitem
    mediaitem = container.mediacollection_service.get_item_latest()

    response = client.get(f"/filter/{mediaitem.id}?filter=original")

    assert response.status_code == 200

    try:
        with Image.open(io.BytesIO(response.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"preview filter did not return valid image bytes, {exc}") from exc


def test_preview_filter_1977(client: TestClient):
    # get the newest mediaitem
    mediaitem = container.mediacollection_service.get_item_latest()

    response = client.get(f"/filter/{mediaitem.id}?filter=FilterPilgram2._1977")

    assert response.status_code == 200

    try:
        with Image.open(io.BytesIO(response.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"preview filter did not return valid image bytes, {exc}") from exc


def test_preview_filter_nonexistentitem(client: TestClient):
    response = client.get(f"/filter/{uuid4()}?filter=original")

    assert response.status_code == 404


def test_preview_otherexception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    mediaitem = container.mediacollection_service.get_item_latest()

    # https://docs.python.org/3/library/unittest.mock.html#where-to-patch
    with patch.object(photobooth.routers.api.filter, "process_image_inner", error_mock):
        response = client.get(f"/filter/{mediaitem.id}?filter=original")

    assert response.status_code == 500


def test_preview_filter_nonexistentfilter(client: TestClient):
    # get the newest mediaitem
    mediaitem = container.mediacollection_service.get_item_latest()

    response = client.get(f"/filter/{mediaitem.id}?filter=FilterPilgram2.theresnofilterlikethis")

    assert response.status_code == 406


def test_apply_filter_nonexistentfilter(client: TestClient):
    # get the newest mediaitem
    mediaitem = container.mediacollection_service.get_item_latest()

    response = client.patch(f"/filter/{mediaitem.id}?filter=FilterPilgram2.theresnofilterlikethis")

    assert response.status_code == 406


def test_apply_filter(client: TestClient):
    # get the newest mediaitem
    mediaitem = container.mediacollection_service.get_item_latest()

    image_before = Image.open(mediaitem.processed)
    image_before.load()  # force load (open is lazy!)

    response = client.patch(f"/filter/{mediaitem.id}?filter=FilterPilgram2._1977")

    assert response.status_code == 200

    if is_same(image_before, Image.open(mediaitem.processed)):
        raise AssertionError("img data before and after same. filter was not applied!")
