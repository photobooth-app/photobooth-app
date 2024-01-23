"""
Testing VIRTUALCAMERA Backend
"""
import logging
import time

import pytest

from photobooth.services.backends.webcamcv2 import WebcamCv2Backend
from photobooth.services.backends.webcamcv2 import available_camera_indexes as cv2_avail
from photobooth.services.config import appconfig

from .backends_utils import get_images

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


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
    appconfig.backends.cv2_CAMERA_TRANSFORM_HFLIP = True
    appconfig.backends.cv2_CAMERA_TRANSFORM_VFLIP = True

    # deliver
    backend.start()
    backend.block_until_device_is_running()
    yield backend
    backend.stop()


def test_get_images_webcamcv2(backend_cv2: WebcamCv2Backend):
    """get lores and hires images from backend and assert"""
    get_images(backend_cv2)


def test_get_video_webcamcv2(backend_cv2: WebcamCv2Backend):
    """get lores and hires images from backend and assert"""
    backend_cv2.start_recording()
    time.sleep(2)
    backend_cv2.stop_recording()

    videopath = backend_cv2.get_recorded_video()
    logger.info(f"video stored to file {videopath}")
    assert videopath and videopath.is_file()
