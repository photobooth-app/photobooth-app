import logging

import pytest

from photobooth.appconfig import appconfig
from photobooth.services.backends.webcamv4l import WebcamV4lBackend, linuxpy_video_device
from photobooth.services.config.groups.cameras import GroupCameraV4l2
from photobooth.utils.enumerate import webcameras

from ..util import block_until_device_is_running, get_images

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


## check skip if wrong platform
if linuxpy_video_device is None:
    pytest.skip("linuxpy module not available", allow_module_level=True)


@pytest.fixture()
def backend_v4l():
    # setup
    backend = WebcamV4lBackend(GroupCameraV4l2())

    logger.info("probing for available cameras")
    _availableCameraIndexes = webcameras()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    cameraIndex = _availableCameraIndexes[0]
    backend._config.HIRES_CAM_RESOLUTION_WIDTH = 640
    backend._config.HIRES_CAM_RESOLUTION_HEIGHT = 480
    backend._config.CAM_RESOLUTION_WIDTH = 640
    backend._config.CAM_RESOLUTION_HEIGHT = 480

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    logger.info(f"using first camera index to test: {cameraIndex}")

    backend._config.device_identifier = str(cameraIndex)

    # deliver
    backend.start()
    block_until_device_is_running(backend)
    yield backend
    backend.stop()


## tests


def test_service_reload(backend_v4l: WebcamV4lBackend):
    """container reloading works reliable"""

    backend_v4l.stop()
    backend_v4l.start()


def test_optimize_mode(backend_v4l: WebcamV4lBackend):
    backend_v4l._on_configure_optimized_for_hq_capture()
    backend_v4l._on_configure_optimized_for_hq_preview()
    backend_v4l._on_configure_optimized_for_idle()


def test_get_images_webcamv4l(backend_v4l: WebcamV4lBackend):
    # get lores and hires images from backend and assert
    backend_v4l._config.switch_to_high_resolution_for_stills = True
    # changing switch_to_high_resolution_for_stills may lead to immediate camera mode change that needs to be waited for
    block_until_device_is_running(backend_v4l)
    get_images(backend_v4l)


def test_get_images_webcamv4l_noswitch_lores(backend_v4l: WebcamV4lBackend):
    # get lores and hires images from backend and assert
    backend_v4l._config.switch_to_high_resolution_for_stills = False
    # changing switch_to_high_resolution_for_stills may lead to immediate camera mode change that needs to be waited for
    block_until_device_is_running(backend_v4l)
    get_images(backend_v4l)


def test_get_images_webcamv4l_yuvy(backend_v4l: WebcamV4lBackend):
    # get lores and hires images from backend and assert
    backend_v4l._config.pixel_format_fourcc = "YUYV"
    backend_v4l.stop()
    backend_v4l.start()
    block_until_device_is_running(backend_v4l)
    get_images(backend_v4l)
