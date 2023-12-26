"""
Testing VIRTUALCAMERA Backend
"""
import logging

import pytest

from photobooth.services.backends.containers import BackendsContainer
from photobooth.services.config import appconfig

from .backends_utils import get_images

logger = logging.getLogger(name=None)


@pytest.fixture()
def backends() -> BackendsContainer:
    # setup
    backends_container = BackendsContainer()
    # deliver
    yield backends_container
    backends_container.shutdown_resources()


def test_get_images_virtualcamera(backends: BackendsContainer):
    virtualcamera_backend = backends.virtualcamera_backend()

    """get lores and hires images from backend and assert"""
    get_images(virtualcamera_backend)


def test_get_images_webcamcv2(backends: BackendsContainer):
    from photobooth.services.backends.webcamcv2 import available_camera_indexes

    logger.info("probing for available cameras")
    _availableCameraIndexes = available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    cameraIndex = _availableCameraIndexes[0]

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    logger.info(f"using first camera index to test: {cameraIndex}")
    appconfig.backends.cv2_device_index = cameraIndex

    """get lores and hires images from backend and assert"""

    webcamcv2_backend = backends.webcamcv2_backend()
    get_images(webcamcv2_backend)
