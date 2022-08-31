#!/usr/bin/python3

# Mostly copied from https://picamera.readthedocs.io/en/release-1.13/recipes2.html
# Run this script, then point a web browser at http:<this-ip-address>:8000
# Note: needs simplejpeg to be installed (pip3 install simplejpeg).

import io
import logging
import socketserver
import time
import numpy as np
import cv2
from http import server
from threading import Condition, Thread

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

from picamera2 import Picamera2, Preview
from picamera2 import Picamera2, MappedArray
from libcamera import Transform
from threading import Timer
import sched
import threading
import time
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration())
capture_config = picam2.create_still_configuration()

# not working in picam2
#picam2.annotate_size = 120 
#picam2.annotate_text = "I am what I am"

countdown=3
remaining_time=3
scheduler = sched.scheduler(time.time, time.sleep)

def some_deferred_task(name):
	picam2.switch_mode_and_capture_file(capture_config, "image.jpg")

colour = (0, 255, 0)
origin = (0, 30)
font = cv2.FONT_HERSHEY_SIMPLEX
scale = 2
thickness = 2
def apply_timestamp(request):
	timestamp = str(remaining_time)
	with MappedArray(request, "main") as m:
		cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness, cv2.FILLED, True)
picam2.pre_callback = apply_timestamp


event_1_id = scheduler.enter(5, 1, some_deferred_task, ('first',))
t = threading.Thread(target=scheduler.run)
t.start()

class test_timer():
	def __init__(self):
		self.awesum="hh"
		self.timer = Timer(1,self.say_hello,args=["WOW"])
		self.timer.start()
	def say_hello(self,message):
		self.awesum=message
		print('HIHIHIIHIH')
		print(message)
		raise Exception("hi")

x=test_timer()


picam2.start_preview(Preview.QTGL, x=100, y=200, width=500, height=300,
transform=Transform(hflip=1))
picam2.start(show_preview=True)

print(picam2.camera_controls)
picam2.set_controls({"ExposureTime": 10000})

time.sleep(5)

#picam2.switch_mode_and_capture_file(capture_config, "image.jpg")