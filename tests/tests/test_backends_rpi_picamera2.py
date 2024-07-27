import logging
import time

import pytest

from photobooth.services.config import appconfig
from photobooth.services.config.groups.backends import GroupBackendPicamera2
from photobooth.utils.helper import is_rpi

from .utils import get_images


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


logger = logging.getLogger(name=None)

## check skip if wrong platform

if not is_rpi():
    pytest.skip(
        "platform not raspberry pi, test of backends skipped",
        allow_module_level=True,
    )


## fixtures


@pytest.fixture()
def backend_picamera2():
    from photobooth.services.backends.picamera2 import Picamera2Backend

    # setup
    backend = Picamera2Backend(GroupBackendPicamera2(optimized_lowlight_short_exposure=True))

    # deliver
    backend.start()
    backend.block_until_device_is_running()
    yield backend
    backend.stop()


## tests


def test_getImages(backend_picamera2):
    get_images(backend_picamera2)


def test_get_video_picamera2(backend_picamera2):
    """get lores and hires images from backend and assert"""
    backend_picamera2.start_recording(5)
    time.sleep(6)
    backend_picamera2.stop_recording()

    videopath = backend_picamera2.get_recorded_video()
    logger.info(f"video stored to file {videopath}")
    assert videopath and videopath.is_file()
