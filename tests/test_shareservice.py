import io
import logging

import pytest
import requests
from dependency_injector import providers
from PIL import Image
from pymitter import EventEmitter

from photobooth.appconfig import AppConfig
from photobooth.services.backends.containers import BackendsContainer
from photobooth.services.containers import ServicesContainer

logger = logging.getLogger(name=None)


## check skip if no shareapi url is set
config = providers.Singleton(AppConfig)
r = requests.get(config().common.shareservice_url, params={"action": "info"})
if not r.status_code == 200:
    logger.warning(f"no webservice found, skipping tests {config().common.shareservice_url}")
    pytest.skip(
        "no webservice found, skipping tests",
        allow_module_level=True,
    )


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture()
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

    # deliver
    services.init_resources()
    yield services
    services.shutdown_resources()


def test_shareservice_urls_valid():
    """test some common actions on url"""
    config = providers.Singleton(AppConfig)

    # /
    r = requests.get(config().common.shareservice_url)
    assert r.status_code == 406

    # info action
    r = requests.get(config().common.shareservice_url, params={"action": "info"})
    logger.info(f"{r.text=}")
    assert r.status_code == 200

    # list action
    r = requests.get(config().common.shareservice_url, params={"action": "list"})
    logger.info(f"{r.text=}")
    assert r.status_code == 200

    # invalid action
    r = requests.get(config().common.shareservice_url, params={"action": "nonexistentaction"})
    logger.info(f"{r.text=}")
    assert r.status_code == 406

    # invalid apikey
    r = requests.post(
        config().common.shareservice_url,
        files=None,
        data={
            "action": "upload",
            "apikey": "wrongapikeyprovided",
            "id": "invalididdoesntmatteranyway",
        },
    )
    logger.info(f"{r.text=}")
    assert r.status_code == 500


def test_shareservice_download_image(services: ServicesContainer):
    """start service and try to download an image"""
    services.config().common.shareservice_enabled = True

    # init share_service when called
    services.share_service()

    # create one image to ensure there is at least one
    services.processing_service().shoot()
    services.processing_service().postprocess()
    services.processing_service().finalize()

    # get the newest image id
    mediaitem_id = services.mediacollection_service().db_get_images()[0]["id"]

    logger.info(f"check to download {mediaitem_id=}")
    r = requests.get(config().common.shareservice_url, params={"action": "download", "id": mediaitem_id})

    # valid status code
    assert r.status_code == 200
    # check we received a valid image also
    try:
        with Image.open(io.BytesIO(r.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"shareservice did not return valid image bytes, {exc}") from exc


def test_shareservice_download_nonexistant_image(services: ServicesContainer):
    """start service and try to download an image that does not exist"""
    services.config().common.shareservice_enabled = True

    # init share_service when called
    services.share_service()

    r = requests.get(config().common.shareservice_url, params={"action": "download", "id": "nonexistentidentifier"})

    # valid status code is 500 because image not existing.
    assert r.status_code == 500
    # despite error, there needs to be delivered an image on this action endpoint,
    # so it can be displayed instead the requested image instead
    try:
        with Image.open(io.BytesIO(r.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"shareservice did not return valid error image bytes, {exc}") from exc


def test_shareservice_reconnect():
    """start service and try service to reconnect if line is temporarily down"""
