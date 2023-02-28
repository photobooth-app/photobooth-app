
import src.test_helperfunctions as test_helperfunctions
from pymitter import EventEmitter
from src.configsettings import settings
import pytest
import platform
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
        if isValidIndex(index):
            arr.append(index)
        index += 1
        i -= 1

    return arr


def isValidIndex(index):
    from v4l2py import Device
    try:
        cap = Device.from_id(index)
        cap.video_capture.set_format(640, 480, 'MJPG')
        for _ in (cap):
            # got frame, close cam and return true; otherwise false.
            break
        cap.close()
    except Exception as e:
        return False
    else:
        return True


def test_getImages():
    if not platform.system() == "Linux":
        pytest.skip("v4l is linux only platform, skipping test")

    from src.imageserverwebcamv4l import ImageServerWebcamV4l

    _availableCameraIndexes = availableCameraIndexes()
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
