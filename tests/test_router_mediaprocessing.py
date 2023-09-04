import io
import logging

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from photobooth.application import ApplicationContainer, app
from photobooth.services.containers import ServicesContainer
from photobooth.services.processing.jobmodels import JobModel

logger = logging.getLogger(name=None)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:

        # create one image to ensure there is at least one
        services=client.app.container.services()
        services.processing_service().start_job_1pic()

        yield client
        client.app.container.shutdown_resources()


def test_preview_filter_original(client: TestClient):
    # get the newest mediaitem
    mediaitem = client.app.container.services().mediacollection_service().db_get_most_recent_mediaitem()

    response = client.get(f"/mediaprocessing/preview/{mediaitem.id}/original")

    assert response.status_code == 200

    try:
        with Image.open(io.BytesIO(response.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"preview filter did not return valid image bytes, {exc}") from exc


def test_preview_filter_1977(client: TestClient):
    # get the newest mediaitem
    mediaitem = client.app.container.services().mediacollection_service().db_get_most_recent_mediaitem()

    response = client.get(f"/mediaprocessing/preview/{mediaitem.id}/_1977")

    assert response.status_code == 200

    try:
        with Image.open(io.BytesIO(response.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"preview filter did not return valid image bytes, {exc}") from exc


def test_preview_filter_nonexistentfilter(client: TestClient):
    # get the newest mediaitem
    mediaitem = client.app.container.services().mediacollection_service().db_get_most_recent_mediaitem()

    response = client.get(f"/mediaprocessing/preview/{mediaitem.id}/theresnofilterlikethis")

    assert response.status_code == 406


def test_apply_filter(client: TestClient):
    # get the newest mediaitem
    mediaitem = client.app.container.services().mediacollection_service().db_get_most_recent_mediaitem()

    image_before = Image.open(mediaitem.path_full)

    response = client.get(f"/mediaprocessing/applyfilter/{mediaitem.id}/_1977")

    assert response.status_code == 200

    if list(image_before.getdata()) == list(Image.open(mediaitem.path_full).getdata()):
        raise AssertionError("img data before and after same. filter was not applied!")


def test_apply_filter_original(client: TestClient):
    # get the newest mediaitem
    mediaitem = client.app.container.services().mediacollection_service().db_get_most_recent_mediaitem()

    response = client.get(f"/mediaprocessing/applyfilter/{mediaitem.id}/original")
    assert response.status_code == 200

    image_original = Image.open(mediaitem.path_preview).copy()

    response = client.get(f"/mediaprocessing/applyfilter/{mediaitem.id}/_1977")
    assert response.status_code == 200
    if list(image_original.getdata()) == list(Image.open(mediaitem.path_preview).getdata()):
        raise AssertionError("img data before and after same. filter was not applied!")

    response = client.get(f"/mediaprocessing/applyfilter/{mediaitem.id}/original")

    assert response.status_code == 200

    assert list(image_original.getdata()) == list(Image.open(mediaitem.path_preview).getdata())

    # need to close image, otherwise pytest hangs!
    image_original.close()
