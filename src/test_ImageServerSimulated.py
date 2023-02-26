import test_HelperFunctions
from pymitter import EventEmitter

# ImageServerSimulated backend: test on every platform
from ImageServerSimulated import ImageServerSimulated
backend = ImageServerSimulated(EventEmitter(), True)


def test_getImages():
    test_HelperFunctions.getImages(backend)
