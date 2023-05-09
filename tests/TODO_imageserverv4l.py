import logging
import platform

# from src.configsettings import settings
import pytest
from pymitter import EventEmitter

from photobooth.containers import ApplicationContainer

from .utils import get_images

logger = logging.getLogger(name=None)

"""
prepare config for testing
"""


## check skip if wrong platform
if not platform.system() == "Linux":
    pytest.skip(
        "v4l is linux only platform, skipping test",
        allow_module_level=True,
    )

## tests


def test_getImages():
    from photobooth.services.backends.webcamv4l import (
        WebcamV4lBackend,
        available_camera_indexes,
    )

    _availableCameraIndexes = available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    cameraIndex = _availableCameraIndexes[0]

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    logger.info(f"using first camera index to test: {cameraIndex}")

    # modify config:
    ApplicationContainer.settings().backends.v4l_device_index = cameraIndex

    # ImageServerSimulated backend: test on every platform
    backend = WebcamV4lBackend(EventEmitter())

    get_images(backend)
