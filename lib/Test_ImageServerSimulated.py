import lib.test_ImageServer as test_ImageServer
from pymitter import EventEmitter

# ImageServerSimulated backend: test on every platform
from ImageServerSimulated import ImageServerSimulated
backend = (ImageServerSimulated(EventEmitter()))


def test_getImages():
    test_ImageServer.getImages(backend)
