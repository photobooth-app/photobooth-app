from .utils import is_rpi, get_images
from pymitter import EventEmitter
from src.configsettings import settings, ConfigSettings, EnumFocuserModule
import pytest
import time
import logging

logger = logging.getLogger(name=None)

## check skip if wrong platform

if not is_rpi():
    pytest.skip(
        "platform not raspberry pi, test of Picam2 backend skipped",
        allow_module_level=True,
    )


def check_focusavail_skip():
    if is_rpi():
        from picamera2 import Picamera2

        with Picamera2() as picam2:
            if "AfMode" not in picam2.camera_controls:
                pytest.skip("SKIPPED (no AF available)")


## fixtures


@pytest.fixture(
    params=[
        EnumFocuserModule.NULL,
        EnumFocuserModule.LIBCAM_AF_INTERVAL,
        EnumFocuserModule.LIBCAM_AF_CONTINUOUS,
    ]
)

## tests


def test_getImages():
    from src.imageserverpicam2 import ImageServerPicam2

    backend = ImageServerPicam2(EventEmitter(), True)

    get_images(backend)


def autofocus_algorithm(request):
    # yield fixture instead return to allow for cleanup:
    yield request.param

    # cleanup
    # os.remove(request.param)


def test_autofocus(autofocus_algorithm):
    check_focusavail_skip()

    from src.imageserverpicam2 import ImageServerPicam2
    from src.configsettings import settings

    evtbus = EventEmitter()

    settings.backends.picam2_focuser_module = autofocus_algorithm
    backend = ImageServerPicam2(evtbus, True)
    backend.start()

    evtbus.emit("statemachine/on_thrill")
    time.sleep(1)
    evtbus.emit("statemachine/on_exit_capture_still")
    time.sleep(1)
    evtbus.emit("onCaptureMode")
    time.sleep(1)
    evtbus.emit("onPreviewMode")
    time.sleep(1)

    # wait so some cycles had happen
    time.sleep(11)

    backend.stop()
