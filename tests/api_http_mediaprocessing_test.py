import io

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from PIL import Image
from pymitter import EventEmitter

from photobooth.appconfig import AppConfig
from photobooth.application import app
from photobooth.services.backends.containers import BackendsContainer
from photobooth.services.containers import ServicesContainer


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        yield client


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def services() -> ServicesContainer:
    # setup
    evtbus = providers.Singleton(EventEmitter)
    config = providers.Singleton(AppConfig)
    services = ServicesContainer(
        evtbus=evtbus,
        config=config,
        backends=BackendsContainer(
            evtbus=evtbus,
            config=config,
        ),
    )

    services.init_resources()

    # create one image to ensure there is at least one
    services.processing_service().shoot()
    services.processing_service().postprocess()
    services.processing_service().finalize()

    # deliver
    yield services
    services.shutdown_resources()


def test_preview_filter_original(client: TestClient, services: ServicesContainer):
    # get the newest mediaitem
    mediaitem = services.mediacollection_service().db_get_images()[0]

    response = client.get(f"/mediaprocessing/preview/{mediaitem.id}/original")

    assert response.status_code == 200

    try:
        with Image.open(io.BytesIO(response.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"preview filter did not return valid image bytes, {exc}") from exc


def test_preview_filter_1977(client: TestClient, services: ServicesContainer):
    # get the newest mediaitem
    mediaitem = services.mediacollection_service().db_get_images()[0]

    response = client.get(f"/mediaprocessing/preview/{mediaitem.id}/_1977")

    assert response.status_code == 200

    try:
        with Image.open(io.BytesIO(response.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"preview filter did not return valid image bytes, {exc}") from exc


def test_preview_filter_nonexistentfilter(client: TestClient, services: ServicesContainer):
    # get the newest mediaitem
    mediaitem = services.mediacollection_service().db_get_images()[0]

    response = client.get(f"/mediaprocessing/preview/{mediaitem.id}/theresnofilterlikethis")

    assert response.status_code == 406


def test_apply_filter(client: TestClient, services: ServicesContainer):
    # get the newest mediaitem
    mediaitem = services.mediacollection_service().db_get_images()[0]

    image_before = Image.open(mediaitem.path_full)

    response = client.get(f"/mediaprocessing/applyfilter/{mediaitem.id}/_1977")

    assert response.status_code == 200

    if list(image_before.getdata()) == list(Image.open(mediaitem.path_full).getdata()):
        raise AssertionError("img data before and after same. filter was not applied!")


def test_apply_filter_original(client: TestClient, services: ServicesContainer):
    # get the newest mediaitem
    mediaitem = services.mediacollection_service().db_get_images()[0]

    image_before = Image.open(mediaitem.path_full)

    response = client.get(f"/mediaprocessing/applyfilter/{mediaitem.id}/original")

    assert response.status_code == 200

    assert list(image_before.getdata()) == list(Image.open(mediaitem.path_full).getdata())
