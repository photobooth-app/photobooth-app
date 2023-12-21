import logging
import time

import pytest
from dependency_injector import providers

from photobooth.appconfig import AppConfig, EnumFocuserModule
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


@pytest.fixture(
    params=[
        EnumFocuserModule.NULL,
        EnumFocuserModule.LIBCAM_AF_INTERVAL,
        EnumFocuserModule.LIBCAM_AF_CONTINUOUS,
    ]
)
def autofocus_algorithm(request):
    # yield fixture instead return to allow for cleanup:
    yield request.param
    # cleanup


## tests


def test_getImages(backends: BackendsContainer):
    picamera2_backend = backends.picamera2_backend()

    get_images(picamera2_backend)


def test_autofocus(autofocus_algorithm, backends: BackendsContainer):
    check_focusavail_skip()

    # reconfigure
    backends.config().backends.picamera2_focuser_module = autofocus_algorithm

    picamera2_backend = backends.picamera2_backend()

    # TODO: test focus changes: picamera2_backend().pause_focus()
    time.sleep(1)

    # wait so some cycles had happen
    time.sleep(1)
