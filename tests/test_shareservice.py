import io
import logging

import pytest
import requests
from PIL import Image

from photobooth.container import Container, container
from photobooth.services.config import appconfig

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


r = requests.get(appconfig.sharing.shareservice_url, params={"action": "info"}, allow_redirects=False)
if not (r.status_code == 200 and "version" in r.text):
    logger.warning(f"no webservice found, skipping tests {appconfig.sharing.shareservice_url}")
    pytest.skip(
        "no webservice found, skipping tests",
        allow_module_level=True,
    )


def test_shareservice_urls_valid():
    """test some common actions on url"""

    # /
    r = requests.get(appconfig.sharing.shareservice_url)
    assert r.status_code == 406

    # info action
    r = requests.get(appconfig.sharing.shareservice_url, params={"action": "info"})
    logger.info(f"{r.text=}")
    assert r.status_code == 200

    # list action
    r = requests.get(appconfig.sharing.shareservice_url, params={"action": "list"})
    logger.info(f"{r.text=}")
    assert r.status_code == 200

    # invalid action
    r = requests.get(appconfig.sharing.shareservice_url, params={"action": "nonexistentaction"})
    logger.info(f"{r.text=}")
    assert r.status_code == 406

    # invalid apikey
    r = requests.post(
        appconfig.sharing.shareservice_url,
        files=None,
        data={
            "action": "upload",
            "apikey": "wrongapikeyprovided",
            "id": "invalididdoesntmatteranyway",
        },
    )
    logger.info(f"{r.text=}")
    assert r.status_code == 500


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Container:
    appconfig.sharing.shareservice_enabled = True

    # setup
    container.start()
    # create one image to ensure there is at least one
    if container.mediacollection_service.number_of_images == 0:
        container.processing_service.start_job_1pic()

    # deliver
    yield container
    container.stop()


def test_shareservice_download_image(_container: Container):
    """start service and try to download an image"""

    # check that share_service was initialized properly, otherwise fail
    assert _container.share_service._initialized

    # get the newest image id
    mediaitem_id = _container.mediacollection_service.db_get_most_recent_mediaitem().id

    logger.info(f"check to download {mediaitem_id=}")
    r = requests.get(
        appconfig.sharing.shareservice_url,
        params={"action": "download", "id": mediaitem_id},
    )

    # valid status code
    assert r.status_code == 200
    # check we received a valid image also
    try:
        with Image.open(io.BytesIO(r.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"shareservice did not return valid image bytes, {exc}") from exc


def test_shareservice_download_nonexistant_image(_container: Container):
    """start service and try to download an image that does not exist"""

    # check that share_service was initialized properly, otherwise fail
    assert _container.share_service._initialized

    r = requests.get(
        appconfig.sharing.shareservice_url,
        params={"action": "download", "id": "nonexistentidentifier"},
    )

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
