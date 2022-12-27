from .ConfigSettings import settings
from libcamera import Transform
from turbojpeg import TurboJPEG, TJPF_RGB, TJSAMP_422
import json
from picamera2 import Picamera2, MappedArray
import psutil
import threading
from threading import Condition, Thread
import cv2
import time
import logging
import FrameServerAbstract
logger = logging.getLogger(__name__)

# helper functions to convert framees (arrays) to jpeg buffer


class FrameServerPicam2(FrameServerAbstract.FrameServerAbstract):
    def do_something(self):
        pass

    def do_something_else(self):
        pass

    def getJpegByHiresFrame(frame, quality):
        jpeg = TurboJPEG()

        jpeg_buffer = jpeg.encode(
            frame, quality=quality, pixel_format=TJPF_RGB, jpeg_subsample=TJSAMP_422)

        return jpeg_buffer

    def getJpegByLoresFrame(frame, quality):
        jpeg = TurboJPEG()

        jpeg_buffer = jpeg.encode(
            frame, quality=quality)

        return jpeg_buffer
