import test_helperfunctions as test_helperfunctions
from pymitter import EventEmitter
import platform
import pytest
import logging
import os
import sys

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


logger = logging.getLogger(name=None)


def _is_rpi():
    is_rpi = False
    if platform.system() == "Linux":
        if os.path.isfile("/proc/device-tree/model"):
            with open("/proc/device-tree/model", "r") as f:
                model = f.read()
                is_rpi = "Raspberry" in model

    return is_rpi


def test_getImages():
    if not _is_rpi():
        pytest.skip("platform not raspberry pi, test of Picam2 backend skipped")
    from src.imageserverpicam2 import ImageServerPicam2

    backend = ImageServerPicam2(EventEmitter(), True)

    test_helperfunctions.get_images(backend)
