from ImageServerWebcamCv2 import ImageServerWebcamCv2
import test_HelperFunctions
import cv2
from pymitter import EventEmitter
import pytest

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

    print(f"available camera indexes: {_availableCameraIndexes}")
    print(f"using first camera index to test: {cameraIndex}")

    # ImageServerSimulated backend: test on every platform
    backend = ImageServerWebcamCv2(EventEmitter(), True)

    test_HelperFunctions.getImages(backend)
