import sys
import os

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.imageserverwebcamcv2 import ImageServerWebcamCv2, available_camera_indexes
import test_helperfunctions as test_helperfunctions
from pymitter import EventEmitter
from src.configsettings import settings
import pytest
import logging

logger = logging.getLogger(name=None)
"""
prepare config for testing
"""


def test_getImages():
    _availableCameraIndexes = available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    cameraIndex = _availableCameraIndexes[0]

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    logger.info(f"using first camera index to test: {cameraIndex}")

    # modify config:
    settings.backends.cv2_device_index = cameraIndex

    # ImageServerSimulated backend: test on every platform
    backend = ImageServerWebcamCv2(EventEmitter(), True)

    test_helperfunctions.get_images(backend)
