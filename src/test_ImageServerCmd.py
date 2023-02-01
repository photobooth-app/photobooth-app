import src.test_ImageServer as test_ImageServer
from pymitter import EventEmitter

# ImageServerCmd backend: test on every platform but needs preparement. (digicamcontrol/gphoto, ...)
from ImageServerCmd import ImageServerCmd
backend = (ImageServerCmd(EventEmitter()))


def test_getImages():
    test_ImageServer.getImages(backend)
