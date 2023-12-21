import logging

import pytest
from dependency_injector import providers

from photobooth.appconfig import AppConfig
from photobooth.services.backends.containers import BackendsContainer
from photobooth.utils.helper import is_rpi

from .backends_utils import get_images

logger = logging.getLogger(name=None)

## check skip if wrong platform

if not is_rpi():
    pytest.skip(
        "platform not raspberry pi, test of backends skipped",
        allow_module_level=True,
    )


def check_focusavail_skip():
    if is_rpi():
        from picamera2 import Picamera2

        with Picamera2() as picamera2:
            if "AfMode" not in picamera2.camera_controls:
                pytest.skip("SKIPPED (no AF available)")


## fixtures


@pytest.fixture()
def backends() -> BackendsContainer:
    # setup
    backends_container = BackendsContainer(
        config=providers.Singleton(AppConfig),
    )
    # deliver
    yield backends_container
    backends_container.shutdown_resources()


## tests


def test_getImages(backends: BackendsContainer):
    picamera2_backend = backends.picamera2_backend()

    get_images(picamera2_backend)
