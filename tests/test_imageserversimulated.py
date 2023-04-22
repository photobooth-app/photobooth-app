"""
Testing Simulated Backend
"""
import logging
from pymitter import EventEmitter
from src.imageserversimulated import ImageServerSimulated
from .utils import get_images

logger = logging.getLogger(name=None)

# ImageServerSimulated backend: test on every platform
backend = ImageServerSimulated(EventEmitter(), True)


def test_get_images():
    """get lores and hires images from backend and assert"""
    get_images(backend)
