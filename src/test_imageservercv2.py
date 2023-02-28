from src.imageserverwebcamcv2 import ImageServerWebcamCv2
import src.test_helperfunctions as test_helperfunctions
import cv2
from pymitter import EventEmitter
from src.configsettings import settings
import pytest
import logging

logger = logging.getLogger(name=None)
"""
prepare config for testing
"""


def availableCameraIndexes():
    # checks the first 10 indexes.

    index = 0
    arr = []
    i = 10
    while i > 0:
        cap = cv2.VideoCapture(index)
        if cap.read()[0]:
            arr.append(index)
            cap.release()
        index += 1
        i -= 1

    return arr


def test_getImages():
    _availableCameraIndexes = availableCameraIndexes()
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
