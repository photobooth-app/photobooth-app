from src.imageserversimulated import ImageServerSimulated
from src.imageservers import ImageServers
import io
from PIL import Image
from .utils import get_images
from pymitter import EventEmitter
from src.configsettings import settings
import pytest
from src.configsettings import (
    settings,
    ConfigSettings,
    EnumImageBackendsMain,
    EnumImageBackendsLive,
)
import logging

logger = logging.getLogger(name=None)
"""
prepare config for testing
"""


def test_getimages_frommultiple_backends():
    # modify config:
    settings.backends.LIVEPREVIEW_ENABLED = True
    settings.backends.MAIN_BACKEND = EnumImageBackendsMain.IMAGESERVER_SIMULATED
    settings.backends.LIVE_BACKEND = EnumImageBackendsLive.IMAGESERVER_SIMULATED

    imageservers = ImageServers(EventEmitter())
    imageservers.start()

    with Image.open(io.BytesIO(imageservers.wait_for_hq_image())) as img:
        img.verify()

    # TODO: test gen_stream()

    imageservers.stop()
