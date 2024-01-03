import io
import logging
import shutil
from pathlib import Path
from random import randrange

import pytest
import requests
from PIL import Image
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Request, Response

from photobooth.services.backends.digicamcontrol import DigicamcontrolBackend
from photobooth.services.config import appconfig

from .backends_utils import get_images

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


@pytest.fixture()
def backend_digicamcontrol_emulated(httpserver: HTTPServer):
    # setup

    def handler_liveview_response(request: Request):
        # deliver some random images.
        # every second frame is the last_image delivered to test the exception handling.

        try:
            output_bytes = handler_liveview_response.last_image  # local static var
            del handler_liveview_response.last_image
        except:
            image = Image.new(mode="RGB", size=(20, 20), color=(randrange(255), randrange(255), randrange(255)))
            with io.BytesIO() as output:
                image.save(output, format="jpeg")
                output_bytes = output.getvalue()
                handler_liveview_response.last_image = output_bytes  # local static var

        return Response(output_bytes, mimetype="image/jpeg")

    def handler_set_tempfolder_and_prepare_output_image(request: Request):
        logger.warning("hit custom handler_set_tempfolder_and_prepare_output_image")
        if request.args.get("slc") == "set" and request.args.get("param1") == "session.folder" and request.args.get("param2"):
            logger.info(request.args)
            target_folder = Path(request.args.get("param2"))
            shutil.copy2("tests/assets/input.jpg", Path(target_folder, "input.jpg"))

            return Response("OK", content_type="text/plain")
        logger.warning("hit custom handler 500 out")
        return Response("illegal request", 500)

    httpserver.host = "127.0.0.1"  # force ipv4 since httpserver listens only on ipv4 ip but localhost resolves to ipv6 address first
    appconfig.backends.digicamcontrol_base_url = httpserver.url_for("/")
    logger.info(f"set mockup testserver: {appconfig.backends.digicamcontrol_base_url}")

    httpserver.expect_request("/", query_string="CMD=LiveViewWnd_Show", method="GET").respond_with_data("OK", content_type="text/plain")
    httpserver.expect_request("/", query_string="CMD=LiveViewWnd_Hide", method="GET").respond_with_data("OK", content_type="text/plain")
    httpserver.expect_request("/", query_string="CMD=All_Minimize", method="GET").respond_with_data("OK", content_type="text/plain")
    httpserver.expect_request("/", query_string="slc=list&param1=cameras&param2=", method="GET").respond_with_data("camera1mockup")
    httpserver.expect_request("/", query_string="slc=capture&param1=&param2=", method="GET").respond_with_data("OK")
    httpserver.expect_oneshot_request("/", query_string="slc=get&param1=lastcaptured&param2=", method="GET").respond_with_data("?")
    httpserver.expect_oneshot_request("/", query_string="slc=get&param1=lastcaptured&param2=", method="GET").respond_with_data("-")
    httpserver.expect_request("/", query_string="slc=get&param1=lastcaptured&param2=", method="GET").respond_with_data("input.jpg")
    httpserver.expect_request("/", method="GET").respond_with_handler(handler_set_tempfolder_and_prepare_output_image)
    httpserver.expect_request("/liveview.jpg", method="GET").respond_with_handler(handler_liveview_response)

    backend = DigicamcontrolBackend()

    # deliver
    backend.start()
    backend.block_until_device_is_running()
    yield backend
    backend.stop()

    httpserver.check_assertions()  # this will raise AssertionError and make the test failing


def test_emulated_get_images_disable_liveview_recovery_more_retries(backend_digicamcontrol_emulated: DigicamcontrolBackend):
    # ensure its working fine.
    get_images(backend_digicamcontrol_emulated)

    # disable live view
    session = requests.Session()
    r = session.get(f"{appconfig.backends.digicamcontrol_base_url}/?CMD=LiveViewWnd_Hide")
    assert r.status_code == 200
    if not r.ok:
        raise AssertionError(f"error disabling liveview {r.status_code} {r.text}")

    # check if recovers, but with some more retries for slow test-computer
    try:
        with Image.open(io.BytesIO(backend_digicamcontrol_emulated.wait_for_lores_image(20))) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc
