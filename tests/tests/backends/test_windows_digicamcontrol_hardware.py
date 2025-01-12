import io
import logging
import platform
import time
from collections.abc import Generator

import pytest
import requests
from PIL import Image

from photobooth.services.backends.digicamcontrol import DigicamcontrolBackend
from photobooth.services.config.groups.backends import GroupBackendDigicamcontrol

from ..utils import get_images

logger = logging.getLogger(name=None)


@pytest.fixture()
def backend_digicamcontrol_hardware() -> Generator[DigicamcontrolBackend, None, None]:
    ## check skip if wrong platform
    if not platform.system() == "Windows":
        pytest.skip("tests are windows only platform, skipping test", allow_module_level=True)

    backend = DigicamcontrolBackend(GroupBackendDigicamcontrol())

    logger.info("probing for available cameras")
    _availableCameraIndexes = backend.available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test", allow_module_level=True)

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    # setup

    # deliver
    backend.start()
    backend._device_enable_lores_flag = True
    backend.block_until_device_is_running()
    yield backend
    backend.stop()


def test_get_images_digicamcontrol(backend_digicamcontrol_hardware: DigicamcontrolBackend):
    # get lores and hires images from backend and assert

    get_images(backend_digicamcontrol_hardware)


def test_get_images_disable_liveview_recovery(backend_digicamcontrol_hardware: DigicamcontrolBackend):
    # get one image to ensure it's working
    get_images(backend_digicamcontrol_hardware)

    # disable liveview to test exceptions and if it recovers properly
    session = requests.Session()
    r = session.get(f"{backend_digicamcontrol_hardware._config.base_url}/?CMD=LiveViewWnd_Hide")
    assert r.status_code == 200
    if not r.ok:
        raise AssertionError(f"error disabling liveview {r.status_code} {r.text}")

    get_images(backend_digicamcontrol_hardware)


def test_get_images_disable_liveview_recovery_more_retries(backend_digicamcontrol_hardware: DigicamcontrolBackend):
    # ensure its working fine.
    get_images(backend_digicamcontrol_hardware)

    # disable live view
    session = requests.Session()
    r = session.get(f"{backend_digicamcontrol_hardware._config.base_url}/?CMD=LiveViewWnd_Hide")
    assert r.status_code == 200
    if not r.ok:
        raise AssertionError(f"error disabling liveview {r.status_code} {r.text}")

    # wait some time until the backend service can acutally detect the error and escalate
    # after escalation it takes some time to reconnect to camera again.
    time.sleep(8)  # escalation takes up to 0.5s*10 retries, see implementation!
    backend_digicamcontrol_hardware.block_until_device_is_running()

    # check if recovers, but with some more retries for slow test-computer
    try:
        with Image.open(io.BytesIO(backend_digicamcontrol_hardware.wait_for_lores_image(50))) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc
