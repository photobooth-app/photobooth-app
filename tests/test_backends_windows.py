import io
import logging
import platform

import pytest
import requests
from PIL import Image

from photobooth.services.backends.digicamcontrol import DigicamcontrolBackend
from photobooth.services.config import appconfig

from .backends_utils import get_images


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


logger = logging.getLogger(name=None)


## check skip if wrong platform
if not platform.system() == "Windows":
    pytest.skip("tests are windows only platform, skipping test", allow_module_level=True)

logger.info("probing for available cameras")
_availableCameraIndexes = DigicamcontrolBackend.available_camera_indexes()
if not _availableCameraIndexes:
    pytest.skip("no camera found, skipping test", allow_module_level=True)

logger.info(f"available camera indexes: {_availableCameraIndexes}")


@pytest.fixture()
def backend_digicamcontrol() -> DigicamcontrolBackend:
    # setup
    backend = DigicamcontrolBackend()

    # deliver
    backend.start()
    yield backend
    backend.stop()


def test_get_images_digicamcontrol(backend_digicamcontrol: DigicamcontrolBackend):
    # get lores and hires images from backend and assert

    get_images(backend_digicamcontrol)


def test_get_images_disable_liveview_recovery(backend_digicamcontrol: DigicamcontrolBackend):
    # get one image to ensure it's working
    get_images(backend_digicamcontrol)

    # disable liveview to test exceptions and if it recovers properly
    session = requests.Session()
    r = session.get(f"{appconfig.backends.digicamcontrol_base_url}/?CMD=LiveViewWnd_Hide")
    assert r.status_code == 200
    if not r.ok:
        raise AssertionError(f"error disabling liveview {r.status_code} {r.text}")

    get_images(backend_digicamcontrol)


def test_get_images_disable_liveview_recovery_more_retries(backend_digicamcontrol: DigicamcontrolBackend):
    # ensure its working fine.
    get_images(backend_digicamcontrol)

    # disable live view
    session = requests.Session()
    r = session.get(f"{appconfig.backends.digicamcontrol_base_url}/?CMD=LiveViewWnd_Hide")
    assert r.status_code == 200
    if not r.ok:
        raise AssertionError(f"error disabling liveview {r.status_code} {r.text}")

    # check if recovers, but with some more retries for slow test-computer
    try:
        with Image.open(io.BytesIO(backend_digicamcontrol.wait_for_lores_image(20))) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc
