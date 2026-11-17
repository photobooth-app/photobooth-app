import logging

import pytest

from photobooth.utils.enumerate import dslr_gphoto2, serial_ports, webcameras

logger = logging.getLogger(name=None)


def test_enum_dslr_gphoto2():

    try:
        dslr_gphoto2()
    except ImportError:
        pytest.skip(reason="gphoto2 not available")


def test_enum_webcameras():
    webcameras()


def test_enum_serial():
    serial_ports()
