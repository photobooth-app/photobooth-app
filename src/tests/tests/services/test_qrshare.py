import io
import logging
from collections.abc import Generator
from uuid import uuid4

import pytest
import requests
from PIL import Image

from photobooth.appconfig import appconfig
from photobooth.container import Container, container
from photobooth.database.models import Mediaitem

logger = logging.getLogger(name=None)

r = requests.get(appconfig.qrshare.shareservice_url, params={"action": "info"}, allow_redirects=False)
is_valid_service = False
try:
    is_valid_service = "version" in list(r.json().keys())
except Exception:
    is_valid_service = False

if not is_valid_service:
    logger.warning(f"no webservice found, skipping tests {appconfig.qrshare.shareservice_url}")
    pytest.skip("no webservice found, skipping tests", allow_module_level=True)


@pytest.fixture(scope="module")
def _container() -> Generator[Container, None, None]:
    appconfig.qrshare.enabled = True

    container.start()
    yield container
    container.stop()


# @pytest.fixture()
@pytest.fixture(params=["image", "collage", "animation", "video"])
def _mediaitem(request, _container: Container) -> Generator[Mediaitem, None, None]:
    _container.processing_service.trigger_action(request.param)
    container.processing_service.wait_until_job_finished()
    yield _container.mediacollection_service.get_item_latest()


def test_shareservice_landingpage_valid():
    # ensure that the landingpage is available - this is a default configured address and helps the user during setup of a booth
    r = requests.get("https://photobooth-app.org/extras/shareservice-landing/")
    assert r.ok


def test_shareservice_urls_valid():
    """test some common actions on url"""

    # /
    r = requests.get(appconfig.qrshare.shareservice_url)
    assert r.status_code == 406

    # info action
    r = requests.get(appconfig.qrshare.shareservice_url, params={"action": "info"})
    logger.info(f"{r.text=}")
    assert r.status_code == 200

    # invalid action
    r = requests.get(appconfig.qrshare.shareservice_url, params={"action": "nonexistentaction"})
    logger.info(f"{r.text=}")
    assert r.status_code == 406

    # invalid apikey
    r = requests.post(
        appconfig.qrshare.shareservice_url,
        files=None,
        data={
            "action": "upload",
            "apikey": "wrongapikeyprovided",
            "id": "invalididdoesntmatteranyway",
        },
    )
    logger.info(f"{r.text=}")
    assert r.status_code == 500


def test_shareservice_download_all_mediaitem_types(_mediaitem: Mediaitem):
    """start service and try to download an image"""

    logger.info(f"check to download {_mediaitem.id=}, {_mediaitem.media_type=}")
    r = requests.get(
        appconfig.qrshare.shareservice_url,
        params={"action": "download", "id": str(_mediaitem.id)},
    )

    # valid status code
    assert r.status_code == 200

    # check we received something
    assert len(r.content) > 0


def test_shareservice_download_nonexistant_image(_container: Container):
    """start service and try to download an image that does not exist"""

    r = requests.get(
        appconfig.qrshare.shareservice_url,
        params={"action": "download", "id": uuid4().hex},
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
