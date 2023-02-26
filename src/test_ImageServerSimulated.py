from ImageServerSimulated import ImageServerSimulated
import test_HelperFunctions
from pymitter import EventEmitter
import logging
logger = logging.getLogger(name=None)

# ImageServerSimulated backend: test on every platform
backend = ImageServerSimulated(EventEmitter(), True)


def test_getImages():
    test_HelperFunctions.getImages(backend)
