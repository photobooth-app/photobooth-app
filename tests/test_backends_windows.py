import logging
import platform
import time

import pytest

from photobooth.services.backends.digicamcontrol import DigicamcontrolBackend

from .backends_utils import get_images

logger = logging.getLogger(name=None)


## check skip if wrong platform
if not platform.system() == "Windows":
    pytest.skip(
        "tests are windows only platform, skipping test",
        allow_module_level=True,
    )


@pytest.fixture()
def backend_digicamcontrol() -> DigicamcontrolBackend:
    # setup
    backend = DigicamcontrolBackend()

    logger.info("probing for available cameras")
    _availableCameraIndexes = backend.available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    logger.info(f"available camera indexes: {_availableCameraIndexes}")

    time.sleep(2)  # wait little time until backend is ready to deliver. otherwise HQ image would miss the event to trigger

    # backends_container.config().backends.digicamcontrol_base_url = httpserver.url_for("/")
    # logger.info(f"set mockup testserver: {backends_container.config().backends.digicamcontrol_base_url}")

    # with open("tests/assets/input_lores.jpg", "rb") as file:
    #     in_file_read = file.read()

    # httpserver.expect_request("/", query_string="CMD=LiveViewWnd_Show", method="GET").respond_with_data("OK")
    # httpserver.expect_request("/", query_string="CMD=All_Minimize", method="GET").respond_with_data("OK")
    # httpserver.expect_request("/", query_string="slc=list&param1=cameras&param2=", method="GET").respond_with_data("camera1mockup")
    # httpserver.expect_request("/", query_string="slc=set&param1=session.folder&param2=", method="GET").respond_with_data("OK")
    # httpserver.expect_request("/", query_string="slc=set&param1=session.filenametemplate&param2=", method="GET").respond_with_data("OK")
    # httpserver.expect_request("/", query_string="slc=capture&param1=&param2=", method="GET").respond_with_data("OK")
    # httpserver.expect_request("/liveview.jpg", method="GET").respond_with_data(in_file_read, mimetype="image/jpeg")
    # httpserver.expect_request("/", method="GET").respond_with_data("OK")

    # deliver
    backend.start()
    yield backend
    backend.stop()


def test_get_images_digicamcontrol(backend_digicamcontrol: DigicamcontrolBackend):
    # get lores and hires images from backend and assert

    get_images(backend_digicamcontrol)
