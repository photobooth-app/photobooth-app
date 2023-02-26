import test_HelperFunctions
from pymitter import EventEmitter
import platform
import pytest


def test_getImages():
    if not platform.system() == "Linux":
        pytest.skip("not on linux, test of Picam2 backend skipped")

    from ImageServerPicam2 import ImageServerPicam2
    backend = ImageServerPicam2(EventEmitter())
    test_HelperFunctions.getImages(backend)
