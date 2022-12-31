import Test_ImageServer
from pymitter import EventEmitter

# ImageServerSimulated backend: test on linux/rpi only
from ImageServerPicam2 import ImageServerPicam2
backend = (ImageServerPicam2(EventEmitter()))


def test_getImages():
    Test_ImageServer.getImages(backend)
