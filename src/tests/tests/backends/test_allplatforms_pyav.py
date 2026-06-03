import logging
from collections.abc import Generator

import pytest

from photobooth.services.backends.webcampyav import WebcamPyavBackend
from photobooth.services.config.groups.cameras import GroupCameraPyav
from photobooth.utils.enumerate import webcameras

from ..util import block_until_device_is_running, get_images

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def backend_pyav() -> Generator[WebcamPyavBackend, None, None]:
    # setup
    backend = WebcamPyavBackend(GroupCameraPyav())

    logger.info("probing for available cameras")
    avail_cams = webcameras()
    if not avail_cams:
        pytest.skip("no camera found, skipping test")

    cameraIndex = avail_cams[0]

    logger.info(f"available camera indexes: {avail_cams}")
    logger.info(f"using first camera index to test: {cameraIndex}")

    backend._config.device_identifier = cameraIndex
    # select a low resolution that all cameras are capable of
    backend._config.cam_resolution_width = 640
    backend._config.cam_resolution_height = 480
    # backend._config.cam_framerate = 30

    # deliver
    backend.start()
    block_until_device_is_running(backend)
    yield backend
    backend.stop()


def test_optimize_mode(backend_pyav: WebcamPyavBackend):
    backend_pyav._handle_switchmode_still_mode()
    backend_pyav._handle_switchmode_video_mode()
    backend_pyav._handle_switchmode_standby()


def test_get_images_webcampyav(backend_pyav: WebcamPyavBackend):
    """get lores and hires images from backend and assert"""
    get_images(backend_pyav)
