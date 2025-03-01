"""
Testing VIRTUALCAMERA Backend
"""

import logging
from collections.abc import Generator

import pytest

from photobooth.services.backends.webcamcv2 import WebcamCv2Backend
from photobooth.services.backends.webcamcv2 import available_camera_indexes as cv2_avail
from photobooth.services.config.groups.backends import GroupBackendOpenCv2

from ..util import get_images

logger = logging.getLogger(name=None)


@pytest.fixture()
def backend_cv2() -> Generator[WebcamCv2Backend, None, None]:
    # setup
    backend = WebcamCv2Backend(GroupBackendOpenCv2())

    logger.info("probing for available cameras")
    _availableCameraIndexes = cv2_avail()
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


def test_service_reload(backend_cv2):
    """container reloading works reliable"""

    for _ in range(1, 5):
        backend_cv2.stop()
        backend_cv2.start()


def test_assert_is_alive(backend_cv2):
    assert backend_cv2._device_alive()


def test_check_avail(backend_cv2):
    backend_cv2.stop()  # for avail check backend not allowed to access it
    assert backend_cv2._device_available()


def test_optimize_mode(backend_cv2):
    backend_cv2._on_configure_optimized_for_hq_capture()
    backend_cv2._on_configure_optimized_for_hq_preview()
    backend_cv2._on_configure_optimized_for_idle()


def test_get_images_webcamcv2(backend_cv2: WebcamCv2Backend):
    """get lores and hires images from backend and assert"""
    get_images(backend_cv2)
