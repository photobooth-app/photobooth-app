"""
Testing VIRTUALCAMERA Backend
"""

import logging
from collections.abc import Generator

import pytest

from photobooth.services.backends.webcampyav import WebcamPyavBackend
from photobooth.services.backends.webcampyav import available_cameras as pyav_avail
from photobooth.services.config.groups.backends import GroupBackendPyav

from ..util import get_images

logger = logging.getLogger(name=None)


@pytest.fixture()
def backend_pyav() -> Generator[WebcamPyavBackend, None, None]:
    # setup
    backend = WebcamPyavBackend(GroupBackendPyav())

    logger.info("probing for available cameras")
    _availableCameraIndexes = pyav_avail()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    cameraIndex = _availableCameraIndexes[0]

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    logger.info(f"using first camera index to test: {cameraIndex}")

    backend._config.device_identifier = cameraIndex
    # select a low resolution that all cameras are capable of
    backend._config.cam_resolution_width = 640
    backend._config.cam_resolution_height = 480

    # deliver
    backend.start()
    backend.block_until_device_is_running()
    yield backend
    backend.stop()


def test_service_reload(backend_pyav):
    """container reloading works reliable"""

    for _ in range(1, 5):
        backend_pyav.stop()
        backend_pyav.start()


def test_assert_is_alive(backend_pyav):
    assert backend_pyav._device_alive()


def test_check_avail(backend_pyav):
    backend_pyav.stop()  # for avail check backend not allowed to access it
    assert backend_pyav._device_available()


def test_optimize_mode(backend_pyav):
    backend_pyav._on_configure_optimized_for_hq_capture()
    backend_pyav._on_configure_optimized_for_hq_preview()
    backend_pyav._on_configure_optimized_for_idle()


def test_get_images_webcampyav(backend_pyav: WebcamPyavBackend):
    """get lores and hires images from backend and assert"""
    get_images(backend_pyav)
