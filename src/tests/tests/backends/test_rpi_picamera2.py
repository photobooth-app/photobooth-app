import logging
import time
from unittest.mock import patch

import pytest

from photobooth.appconfig import appconfig
from photobooth.services.config.groups.backends import GroupBackendPicamera2
from photobooth.utils.helper import is_rpi

from ..util import get_images


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


logger = logging.getLogger(name=None)

## check skip if wrong platform

if not is_rpi():
    pytest.skip("platform not raspberry pi, test of backends skipped", allow_module_level=True)


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


def test_service_reload(backend_picamera2):
    """container reloading works reliable"""

    for _ in range(1, 5):
        backend_picamera2.stop()
        backend_picamera2.start()


def test_picamera2_switch_modes(backend_picamera2):
    with patch.object(backend_picamera2._picamera2, "switch_mode"):
        backend_picamera2._on_configure_optimized_for_hq_capture()
        backend_picamera2.wait_for_lores_image()  # wait until next frame avail, because it should have switched by then
        # hq-capture does not change actually because change happens in hq preview already.
        backend_picamera2._picamera2.switch_mode.assert_not_called()

    with patch.object(backend_picamera2._picamera2, "switch_mode"):
        backend_picamera2._on_configure_optimized_for_hq_preview()
        backend_picamera2.wait_for_lores_image()  # wait until next frame avail, because it should have switched by then
        backend_picamera2._picamera2.switch_mode.assert_called()

    with patch.object(backend_picamera2._picamera2, "switch_mode"):
        backend_picamera2._on_configure_optimized_for_idle()
        backend_picamera2.wait_for_lores_image()  # wait until next frame avail, because it should have switched by then
        backend_picamera2._picamera2.switch_mode.assert_called()


def test_assert_is_alive(backend_picamera2):
    assert backend_picamera2._device_alive()


def test_check_avail(backend_picamera2):
    assert backend_picamera2._device_available()


def test_getImages(backend_picamera2):
    get_images(backend_picamera2)


def test_get_video_picamera2(backend_picamera2):
    """get lores and hires images from backend and assert"""
    videopath = backend_picamera2.start_recording(video_framerate=5)
    time.sleep(2)
    backend_picamera2.stop_recording()

    logger.info(f"video stored to file {videopath}")
    assert videopath and videopath.is_file()
