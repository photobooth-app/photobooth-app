import io
import logging
import os
import platform

import pytest
from dependency_injector import providers
from PIL import Image
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


def use_vcam():
    import gphoto2 as gp

    logger.info(f"python-gphoto2: {gp.__version__}")

    # virtual camera delivers images from following path:
    os.environ["VCAMERADIR"] = os.path.join(os.path.dirname(__file__), "assets")
    # switch to virtual camera from normal drivers
    os.environ["IOLIBS"] = os.environ["IOLIBS"].replace("iolibs", "vusb")
    logger.info(os.environ["VCAMERADIR"])
    logger.info(os.environ["IOLIBS"])


def has_vcam():
    import gphoto2 as gp

    vusb_dir = os.environ["IOLIBS"].replace("iolibs", "vusb")
    if not os.path.isdir(vusb_dir):
        logger.warning(f"missing {vusb_dir=}")
        return False
    gp_library_version = gp.gp_library_version(gp.GP_VERSION_SHORT)[0]
    gp_library_version = tuple(int(x) for x in gp_library_version.split("."))
    if gp_library_version > (2, 5, 30):
        return True

    logger.warning("gp_library_version too old")
    return False


@pytest.fixture()
def backends() -> BackendsContainer:
    # setup
    backends_container = BackendsContainer(
        evtbus=providers.Singleton(EventEmitter),
        config=providers.Singleton(AppConfig),
    )
    # deliver
    yield backends_container
    backends_container.shutdown_resources()


## tests


def test_get_images_webcamv4l(backends: BackendsContainer):
    from photobooth.services.backends.webcamv4l import available_camera_indexes

    logger.info("probing for available cameras")
    _availableCameraIndexes = available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    cameraIndex = _availableCameraIndexes[0]

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    logger.info(f"using first camera index to test: {cameraIndex}")
    backends.config().backends.v4l_device_index = cameraIndex

    # get lores and hires images from backend and assert
    webcamv4l_backend = backends.webcamv4l_backend()
    get_images(webcamv4l_backend)


def test_get_images_gphoto2(backends: BackendsContainer):
    use_vcam()
    logger.info(has_vcam())

    from photobooth.services.backends.gphoto2 import available_camera_indexes

    _availableCameraIndexes = available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    # its checked whether camera is available, but actually never used the index, because it's assumed
    # only one DSLR is connected at a time.

    # get lores and hires images from backend and assert
    gphoto2_backend = backends.gphoto2_backend()

    if not gphoto2_backend._camera_preview_available:
        with pytest.raises(RuntimeError):
            with Image.open(io.BytesIO(gphoto2_backend._wait_for_lores_image())) as img:
                img.verify()

    with Image.open(io.BytesIO(gphoto2_backend.wait_for_hq_image())) as img:
        img.verify()


def test_get_gphoto2_info():
    import gphoto2 as gp

    logger.info(f"python-gphoto2: {gp.__version__}")
    logger.info(f"libgphoto2: {gp.gp_library_version(gp.GP_VERSION_VERBOSE)}")
    logger.info(f"libgphoto2_port: {gp.gp_port_library_version(gp.GP_VERSION_VERBOSE)}")
