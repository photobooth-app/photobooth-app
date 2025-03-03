import logging

import pytest

from photobooth.appconfig import appconfig
from photobooth.services.backends.webcamv4l import WebcamV4lBackend, linuxpy_video_device
from photobooth.services.backends.webcamv4l import available_camera_indexes as v4l_avail
from photobooth.services.config.groups.backends import GroupBackendV4l2

from ..util import get_images

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


## check skip if wrong platform
if linuxpy_video_device is None:
    pytest.skip("linuxpy module not available", allow_module_level=True)


@pytest.fixture()
def backend_v4l():
    # setup
    backend = WebcamV4lBackend(GroupBackendV4l2())

    logger.info("probing for available cameras")
    _availableCameraIndexes = v4l_avail()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    cameraIndex = _availableCameraIndexes[0]

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    logger.info(f"using first camera index to test: {cameraIndex}")

    backend._config.device_index = cameraIndex

    # deliver
    backend.start()
    backend.block_until_device_is_running()
    yield backend
    backend.stop()


## tests


def test_service_reload(backend_v4l):
    """container reloading works reliable"""

    for _ in range(1, 5):
        backend_v4l.stop()
        backend_v4l.start()


def test_assert_is_alive(backend_v4l):
    assert backend_v4l._device_alive()


def test_check_avail(backend_v4l):
    backend_v4l.stop()
    assert backend_v4l._device_available()


def test_optimize_mode(backend_v4l):
    backend_v4l._on_configure_optimized_for_hq_capture()
    backend_v4l._on_configure_optimized_for_hq_preview()
    backend_v4l._on_configure_optimized_for_idle()


def test_get_images_webcamv4l(backend_v4l):
    # get lores and hires images from backend and assert
    backend_v4l._config.switch_to_high_resolution_for_stills = True
    get_images(backend_v4l)


def test_get_images_webcamv4l_noswitch_lores(backend_v4l):
    # get lores and hires images from backend and assert
    backend_v4l._config.switch_to_high_resolution_for_stills = False
    get_images(backend_v4l)
