"""
Testing Simulated Backend
"""
import logging
from pymitter import EventEmitter
import os
import sys

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.imageserversimulated import ImageServerSimulated
from test_helperfunctions import get_images

logger = logging.getLogger(name=None)

# ImageServerSimulated backend: test on every platform
backend = ImageServerSimulated(EventEmitter(), True)


def test_get_images():
    """get lores and hires images from backend and assert"""
    get_images(backend)
