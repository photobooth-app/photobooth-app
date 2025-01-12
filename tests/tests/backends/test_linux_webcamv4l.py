import logging
import platform

import pytest

from photobooth.services.config import appconfig
from photobooth.services.config.groups.backends import GroupBackendV4l2

from ..utils import get_images

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


"""
prepare config for testing
"""


## check skip if wrong platform
if not platform.system() == "Linux":
    pytest.skip(
        "tests are linux only platform, skipping test",
        allow_module_level=True,
    )


@pytest.fixture()
def backend_v4l():
    from photobooth.services.backends.webcamv4l import WebcamV4lBackend
    from photobooth.services.backends.webcamv4l import available_camera_indexes as v4l_avail

    # setup
    backend = WebcamV4lBackend(GroupBackendV4l2())

    logger.info("probing for available cameras")
    _availableCameraIndexes = v4l_avail()
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


## tests


def test_assert_is_alive(backend_v4l):
    assert backend_v4l._device_alive()


def test_get_images_webcamv4l(backend_v4l):
    # get lores and hires images from backend and assert
    get_images(backend_v4l)
