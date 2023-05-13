import logging
import platform

import pytest
from dependency_injector import providers
from pymitter import EventEmitter

from photobooth.appconfig import AppConfig
from photobooth.services.backends.containers import BackendsContainer

from .backends_utils import get_images

logger = logging.getLogger(name=None)

"""
prepare config for testing
"""


## check skip if wrong platform
if not platform.system() == "Linux":
    pytest.skip(
        "tests are linux only platform, skipping test",
        allow_module_level=True,
    )

## tests


def test_get_images_webcamv4l():
    backend = BackendsContainer(
        evtbus=providers.Singleton(EventEmitter), config=providers.Singleton(AppConfig)
    )

    from photobooth.services.backends.webcamv4l import available_camera_indexes

    logger.info("probing for available cameras")
    _availableCameraIndexes = available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    cameraIndex = _availableCameraIndexes[0]

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    logger.info(f"using first camera index to test: {cameraIndex}")
    backend.config().backends.v4l_device_index = cameraIndex

    # get lores and hires images from backend and assert
    webcamv4l_backend = backend.webcamv4l_backend()
    get_images(webcamv4l_backend)


def test_get_images_gphoto2():
    backend = BackendsContainer(
        evtbus=providers.Singleton(EventEmitter), config=providers.Singleton(AppConfig)
    )
    from photobooth.services.backends.gphoto2 import available_camera_indexes

    _availableCameraIndexes = available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    # its checked whether camera is available, but actually never used the index, because it's assumed
    # only one DSLR is connected at a time.

    # get lores and hires images from backend and assert
    gphoto2_backend = backend.gphoto2_backend()
    if not gphoto2_backend._camera_preview_available:
        with pytest.raises(AssertionError):
            get_images(gphoto2_backend)
    else:
        get_images(gphoto2_backend)
