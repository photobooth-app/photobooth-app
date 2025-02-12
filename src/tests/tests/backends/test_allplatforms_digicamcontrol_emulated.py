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
from photobooth.services.config.groups.backends import GroupBackendDigicamcontrol

from ..util import get_images

logger = logging.getLogger(name=None)


@pytest.fixture()
def backend_digicamcontrol_emulated(httpserver: HTTPServer):
    # setup
    backend = DigicamcontrolBackend(GroupBackendDigicamcontrol())

    def handler_liveview_response(request: Request):
        # deliver some random images.
        # every second frame is the last_image delivered to test the exception handling.

        try:
            output_bytes = handler_liveview_response.last_image  # type: ignore # local static var
            del handler_liveview_response.last_image  # type: ignore # local static var
        except Exception:
            image = Image.new(mode="RGB", size=(20, 20), color=(randrange(255), randrange(255), randrange(255)))
            with io.BytesIO() as output:
                image.save(output, format="jpeg")
                output_bytes = output.getvalue()
                handler_liveview_response.last_image = output_bytes  # type: ignore # local static var

        return Response(output_bytes, mimetype="image/jpeg")

    def handler_set_tempfolder_and_prepare_output_image(request: Request):
        logger.warning("hit custom handler_set_tempfolder_and_prepare_output_image")
        if request.args.get("slc") == "set" and request.args.get("param1") == "session.folder" and request.args.get("param2"):
            logger.info(request.args)
            param2 = request.args.get("param2")
            assert param2
            shutil.copy2("src/tests/assets/input.jpg", Path(param2, "input.jpg"))

            return Response("OK", content_type="text/plain")
        logger.warning("hit custom handler 500 out")
        return Response("illegal request", 500)

    httpserver.host = "127.0.0.1"  # force ipv4 since httpserver listens only on ipv4 ip but localhost resolves to ipv6 address first
    backend._config.base_url = httpserver.url_for("/")
    logger.info(f"set mockup testserver: {backend._config.base_url}")

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

    # deliver
    backend.start()
    backend._device_enable_lores_flag = True
    backend.block_until_device_is_running()
    yield backend
    backend.stop()

    httpserver.check_assertions()  # this will raise AssertionError and make the test failing


def test_assert_is_alive(backend_digicamcontrol_emulated: DigicamcontrolBackend):
    assert backend_digicamcontrol_emulated._device_alive()


def test_optimize_mode(backend_digicamcontrol_emulated: DigicamcontrolBackend):
    backend_digicamcontrol_emulated._on_configure_optimized_for_hq_capture()
    backend_digicamcontrol_emulated._on_configure_optimized_for_hq_preview()
    backend_digicamcontrol_emulated._on_configure_optimized_for_idle()


def test_emulated_get_images_disable_liveview_recovery_more_retries(backend_digicamcontrol_emulated: DigicamcontrolBackend):
    # ensure its working fine.
    get_images(backend_digicamcontrol_emulated)

    # disable live view
    session = requests.Session()
    r = session.get(f"{backend_digicamcontrol_emulated._config.base_url}/?CMD=LiveViewWnd_Hide")
    assert r.status_code == 200
    if not r.ok:
        raise AssertionError(f"error disabling liveview {r.status_code} {r.text}")

    # check if recovers, but with some more retries for slow test-computer
    try:
        with Image.open(io.BytesIO(backend_digicamcontrol_emulated.wait_for_lores_image(20))) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc
