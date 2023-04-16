import test_helperfunctions as test_helperfunctions
from pymitter import EventEmitter
from src.configsettings import settings
import pytest
import platform
import logging
import os
import sys

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logger = logging.getLogger(name=None)

"""
prepare config for testing
"""


def test_getImages():
    if not platform.system() == "Linux":
        pytest.skip("v4l is linux only platform, skipping test")

    from src.imageserverwebcamv4l import ImageServerWebcamV4l, available_camera_indexes

    _availableCameraIndexes = available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    cameraIndex = _availableCameraIndexes[0]

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    logger.info(f"using first camera index to test: {cameraIndex}")

    # modify config:
    settings.backends.v4l_device_index = cameraIndex

    # ImageServerSimulated backend: test on every platform
    backend = ImageServerWebcamV4l(EventEmitter(), True)

    test_helperfunctions.get_images(backend)
