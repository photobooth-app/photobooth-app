import logging

import pytest

from photobooth.services.backends.gphoto2 import gp
from photobooth.utils.enumerate import dslr_gphoto2, serial_ports, webcameras

logger = logging.getLogger(name=None)


def test_enum_dslr_gphoto2():
    ## check skip if wrong platform
    if gp is None:
        pytest.skip("gphoto2 not available")

    dslr_gphoto2()


def test_enum_webcameras():
    webcameras()


def test_enum_serial():
    serial_ports()
