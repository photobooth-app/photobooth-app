import io
import logging
import os
import platform

import pytest
from PIL import Image

from photobooth.services.config import appconfig

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
def backend_gphoto2():
    from photobooth.services.backends.gphoto2 import Gphoto2Backend
    from photobooth.services.backends.gphoto2 import available_camera_indexes as gp2_avail
    # ensure virtual camera is available (starting from gphoto2 2.5.0 always true)
    # assert has_vcam() # on selfhosted-runner currently a problem. TODO: setup new RPI runner

    # its checked whether camera is available, but actually never used the index, because it's assumed
    # only one DSLR is connected at a time.

    def use_vcam():
        import gphoto2 as gp

        logger.info(f"python-gphoto2: {gp.__version__}")

        # virtual camera delivers images from following path:
        os.environ["VCAMERADIR"] = os.path.join(os.path.dirname(__file__), "../assets")
        # switch to virtual camera from normal drivers
        # IOLIBS is set on import of gphoto2:
        # https://github.com/jim-easterbrook/python-gphoto2/blob/510149d454c9fa1bd03a43f098eea3c52d2e0675/src/swig-gp2_5_31/__init__.py#L15C32-L15C32
        os.environ["IOLIBS"] = os.environ["IOLIBS"].replace("iolibs", "vusb")

        logger.info(os.environ["VCAMERADIR"])
        logger.info(os.environ["IOLIBS"])

    def has_vcam():
        import gphoto2 as gp

        if "IOLIBS" not in os.environ:
            logger.warning("missing IOLIBS in os.environ! installation is off.")
            return False

        vusb_dir = os.environ["IOLIBS"].replace("iolibs", "vusb")
        if not os.path.isdir(vusb_dir):
            logger.warning(f"missing {vusb_dir=}")
            return False
        gp_library_version = gp.gp_library_version(gp.GP_VERSION_SHORT)[0]
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

    _availableCameraIndexes = gp2_avail()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    backend = Gphoto2Backend()
    # deliver
    backend.start()
    backend.block_until_device_is_running()
    yield backend
    backend.stop()


## tests


def test_get_images_gphoto2(backend_gphoto2):
    # get lores and hires images from backend and assert

    with pytest.raises(RuntimeError):
        with Image.open(io.BytesIO(backend_gphoto2.wait_for_lores_image())) as img:
            img.verify()

    with Image.open(io.BytesIO(backend_gphoto2.wait_for_hq_image())) as img:
        img.verify()


def test_get_images_gphoto2_wait_event(backend_gphoto2):
    # get lores and hires images from backend and assert
    appconfig.backends.gphoto2_wait_event_after_capture_trigger = True

    with pytest.raises(RuntimeError):
        with Image.open(io.BytesIO(backend_gphoto2.wait_for_lores_image())) as img:
            img.verify()

    with Image.open(io.BytesIO(backend_gphoto2.wait_for_hq_image())) as img:
        img.verify()


def test_get_gphoto2_switch_modes(backend_gphoto2):
    backend_gphoto2._on_capture_mode()
    backend_gphoto2._on_preview_mode()

    # change some values
    appconfig.backends.gphoto2_iso_capture = "auto"
    appconfig.backends.gphoto2_iso_liveview = "200"
    appconfig.backends.gphoto2_shutter_speed_capture = "1/20"
    appconfig.backends.gphoto2_shutter_speed_liveview = "1/30"
    backend_gphoto2._on_capture_mode()
    backend_gphoto2._on_preview_mode()

    # and try illegal values that raise exception
    appconfig.backends.gphoto2_iso_capture = "illegal"
    appconfig.backends.gphoto2_iso_liveview = "illegal"
    appconfig.backends.gphoto2_shutter_speed_capture = "illegal"
    appconfig.backends.gphoto2_shutter_speed_liveview = "illegal"
    backend_gphoto2._on_capture_mode()  # should log an error but ignore and continue
    backend_gphoto2._on_preview_mode()  # should log an error but ignore and continue


def test_get_gphoto2_camera_info(backend_gphoto2):
    logger.info(backend_gphoto2._camera.get_summary())

    config = backend_gphoto2._camera.list_config()
    for n in range(len(config)):
        logger.info(f"{config.get_name(n)}, {config.get_value(n)}")


def test_get_gphoto2_info():
    import gphoto2 as gp

    logger.info(f"python-gphoto2: {gp.__version__}")
    logger.info(f"libgphoto2: {gp.gp_library_version(gp.GP_VERSION_VERBOSE)}")
    logger.info(f"libgphoto2_port: {gp.gp_port_library_version(gp.GP_VERSION_VERBOSE)}")
