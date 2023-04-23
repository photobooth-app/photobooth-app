from pymitter import EventEmitter
from src.configsettings import settings
import pytest
import platform
import logging
from .utils import get_images

logger = logging.getLogger(name=None)

"""
prepare config for testing
"""


## check skip if wrong platform
if not platform.system() == "Linux":
    pytest.skip(
        "gphoto2 is linux only platform, skipping test",
        allow_module_level=True,
    )

## tests


def test_getImages():
    from src.imageservergphoto2 import ImageServerGphoto2, available_camera_indexes

    _availableCameraIndexes = available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    backend = ImageServerGphoto2(EventEmitter(), True)

    get_images(backend)
