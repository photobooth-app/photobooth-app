#!/usr/bin/python3

# seems video is abort when picture is taken :(
# if bitrate is added, it seems to work. but problem is, h264 doesn't stream directly to browser. need jpeg or mjpeg for stream
# high quality resolution

import time

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder

# Encode a VGA stream, and capture a higher resolution still image half way through.

picam2 = Picamera2()
main_stream = {"size": picam2.sensor_resolution}
lores_stream = {"size": (640, 480)}
video_config = picam2.create_still_configuration(
    main_stream, lores_stream, encode="lores")
picam2.configure(video_config)

encoder = MJPEGEncoder(bitrate=100000000)

picam2.start_recording(encoder, 'videocapture5.mjpeg')
time.sleep(6)

# It's better to capture the still in this thread, not in the one driving the camera.
request = picam2.capture_request()
request.save("main", "videocapture5.jpg")
request.release()
print("Still image captured!")

time.sleep(10)
picam2.stop_recording()
