import io
import logging
import os
import time

import pytest
from PIL import Image

from photobooth.appconfig import appconfig
from photobooth.services.backends.gphoto2 import Gphoto2Backend, gp
from photobooth.services.config.groups.backends import GroupBackendGphoto2
from photobooth.utils.enumerate import dslr_gphoto2 as enumerate_dslr_gphoto2

from ..util import block_until_device_is_running

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


"""
prepare config for testing
"""


## check skip if wrong platform
if gp is None:
    pytest.skip("gphoto2 not available", allow_module_level=True)


@pytest.fixture()
def backend_gphoto2():
    # ensure virtual camera is available (starting from gphoto2 2.5.0 always true)
    # assert has_vcam() # on selfhosted-runner currently a problem. TODO: setup new RPI runner

    # its checked whether camera is available, but actually never used the index, because it's assumed
    # only one DSLR is connected at a time.

    def use_vcam():
        logger.info(f"python-gphoto2: {gp.__version__}")

        # virtual camera delivers images from following path:
        os.environ["VCAMERADIR"] = os.path.join(os.path.dirname(__file__), "../../assets")
        # switch to virtual camera from normal drivers
        # IOLIBS is set on import of gphoto2:
        # https://github.com/jim-easterbrook/python-gphoto2/blob/510149d454c9fa1bd03a43f098eea3c52d2e0675/src/swig-gp2_5_31/__init__.py#L15C32-L15C32
        os.environ["IOLIBS"] = os.environ["IOLIBS"].replace("iolibs", "vusb")

        logger.info(os.environ["VCAMERADIR"])
        logger.info(os.environ["IOLIBS"])

    def has_vcam():
        if "IOLIBS" not in os.environ:
            logger.warning("missing IOLIBS in os.environ! installation is off.")
            return False

        vusb_dir = os.environ["IOLIBS"].replace("iolibs", "vusb")
        if not os.path.isdir(vusb_dir):
            logger.warning(f"missing {vusb_dir=}")
            return False
        gp_library_version = gp.gp_library_version(gp.GP_VERSION_SHORT)[0]  # pyright: ignore [reportAttributeAccessIssue]
        gp_library_version = tuple(int(x) for x in gp_library_version.split("."))
        if gp_library_version > (2, 5, 30):
            return True

        logger.warning(f"{gp_library_version=} too old. usually libgphoto is delivered with pip package, so this should not happen!")

        return False

    # setup
    if not has_vcam():
        pytest.skip("system installation does not support virtual camera!")

    # use vcam
    use_vcam()

    avail_cams = enumerate_dslr_gphoto2()
    if not avail_cams:
        pytest.skip("no camera found, skipping test")

    backend = Gphoto2Backend(GroupBackendGphoto2())
    # deliver
    backend.start()
    block_until_device_is_running(backend)
    yield backend
    backend.stop()


## tests


def test_service_reload(backend_gphoto2):
    """container reloading works reliable"""

    for _ in range(1, 5):
        backend_gphoto2.stop()
        backend_gphoto2.start()


def test_get_images_gphoto2(backend_gphoto2):
    # get lores and hires images from backend and assert

    with pytest.raises(RuntimeError):
        with Image.open(io.BytesIO(backend_gphoto2.wait_for_lores_image())) as img:
            img.verify()

    with Image.open(backend_gphoto2.wait_for_still_file()) as img:
        img.verify()


def test_get_gphoto2_switch_modes(backend_gphoto2):
    backend_gphoto2._on_configure_optimized_for_hq_capture()

    backend_gphoto2.wait_for_still_file()

    backend_gphoto2._on_configure_optimized_for_hq_preview()
    backend_gphoto2._configure_optimized_for_idle_video()
    time.sleep(1)
    backend_gphoto2._on_configure_optimized_for_idle()
    backend_gphoto2._configure_optimized_for_idle_video()
    time.sleep(1)

    # change some values
    backend_gphoto2._config.iso_capture = "auto"
    backend_gphoto2._config.iso_liveview = "200"
    backend_gphoto2._config.shutter_speed_capture = "1/20"
    backend_gphoto2._config.shutter_speed_liveview = "1/30"
    backend_gphoto2._on_configure_optimized_for_hq_capture()

    backend_gphoto2.wait_for_still_file()

    backend_gphoto2._on_configure_optimized_for_hq_preview()
    backend_gphoto2._configure_optimized_for_idle_video()
    time.sleep(1)
    backend_gphoto2._on_configure_optimized_for_idle()
    backend_gphoto2._configure_optimized_for_idle_video()
    time.sleep(1)

    # and try illegal values that raise exception
    backend_gphoto2._config.iso_capture = "illegal"
    backend_gphoto2._config.iso_liveview = "illegal"
    backend_gphoto2._config.shutter_speed_capture = "illegal"
    backend_gphoto2._config.shutter_speed_liveview = "illegal"
    backend_gphoto2._on_configure_optimized_for_hq_capture()

    backend_gphoto2.wait_for_still_file()

    backend_gphoto2._on_configure_optimized_for_hq_preview()
    backend_gphoto2._configure_optimized_for_idle_video()
    time.sleep(1)
    backend_gphoto2._on_configure_optimized_for_idle()
    backend_gphoto2._configure_optimized_for_idle_video()
    time.sleep(1)


def test_get_gphoto2_camera_info(backend_gphoto2):
    logger.info(backend_gphoto2._camera.get_summary())

    config = backend_gphoto2._camera.list_config()
    for n in range(len(config)):
        logger.info(f"{config.get_name(n)}, {config.get_value(n)}")


def test_get_gphoto2_info():
    logger.info(f"python-gphoto2: {gp.__version__}")
    logger.info(f"libgphoto2: {gp.gp_library_version(gp.GP_VERSION_VERBOSE)}")  # pyright: ignore [reportAttributeAccessIssue]
    logger.info(f"libgphoto2_port: {gp.gp_port_library_version(gp.GP_VERSION_VERBOSE)}")  # pyright: ignore [reportAttributeAccessIssue]
