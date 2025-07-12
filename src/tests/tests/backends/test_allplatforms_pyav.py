import logging
from collections.abc import Generator

import pytest

from photobooth.services.backends.webcampyav import WebcamPyavBackend
from photobooth.services.config.groups.cameras import GroupCameraPyav
from photobooth.utils.enumerate import webcameras

from ..util import block_until_device_is_running, get_images

logger = logging.getLogger(name=None)


@pytest.fixture()
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


def test_service_reload(backend_pyav: WebcamPyavBackend):
    """container reloading works reliable"""

    backend_pyav.stop()
    backend_pyav.start()


def test_optimize_mode(backend_pyav):
    backend_pyav._on_configure_optimized_for_hq_capture()
    backend_pyav._on_configure_optimized_for_hq_preview()
    backend_pyav._on_configure_optimized_for_idle()


def test_get_images_webcampyav(backend_pyav: WebcamPyavBackend):
    """get lores and hires images from backend and assert"""
    get_images(backend_pyav)


# Takes long time until fails - does it add to coverage actually?
# def test_device_wrong_id_fails(backend_pyav: WebcamPyavBackend):
#     backend_pyav.stop()
#     backend_pyav._config.device_identifier = "999"
#     backend_pyav.start()

#     with pytest.raises(RuntimeError):
#         backend_pyav.wait_for_still_file(retries=1)
