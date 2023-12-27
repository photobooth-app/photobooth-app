"""
Testing VIRTUALCAMERA Backend
"""
import logging
from importlib import reload

import pytest

import photobooth.services.config
from photobooth.services.backends.virtualcamera import VirtualCameraBackend
from photobooth.services.backends.webcamcv2 import WebcamCv2Backend
from photobooth.services.backends.webcamcv2 import available_camera_indexes as cv2_avail
from photobooth.services.config import appconfig

from .backends_utils import get_images

reload(photobooth.services.config)  # reset config to defaults.
logger = logging.getLogger(name=None)


@pytest.fixture()
def backend_cv2() -> WebcamCv2Backend:
    # setup
    backend = WebcamCv2Backend()

    logger.info("probing for available cameras")
    _availableCameraIndexes = cv2_avail()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    cameraIndex = _availableCameraIndexes[0]

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    logger.info(f"using first camera index to test: {cameraIndex}")

    appconfig.backends.cv2_device_index = cameraIndex

    # deliver
    backend.start()
    yield backend
    backend.stop()


@pytest.fixture()
def backend_virtual() -> VirtualCameraBackend:
    # setup
    backend = VirtualCameraBackend()

    # deliver
    backend.start()
    yield backend
    backend.stop()


def test_get_images_virtualcamera(backend_virtual: WebcamCv2Backend):
    """get lores and hires images from backend and assert"""
    get_images(backend_virtual)


def test_get_images_webcamcv2(backend_cv2: WebcamCv2Backend):
    """get lores and hires images from backend and assert"""
    get_images(backend_cv2)
