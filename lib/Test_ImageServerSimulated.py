import Test_ImageServer
from pymitter import EventEmitter

# ImageServerSimulated backend: test on every platform
from ImageServerSimulated import ImageServerSimulated
backend = (ImageServerSimulated(EventEmitter()))


def test_getImages():
    Test_ImageServer.getImages(backend)
