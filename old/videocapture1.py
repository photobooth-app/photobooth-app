#!/usr/bin/python3

# seems video is abort when picture is taken :(

import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
# Encode a VGA stream, and capture a higher resolution still image half way through.

picam2 = Picamera2()
main_stream = {"size": picam2.sensor_resolution}
lores_stream = {"size": (640, 480)}
video_config = picam2.create_still_configuration(
    main_stream, lores_stream, encode="lores")
picam2.configure(video_config)

encoder = H264Encoder()

picam2.start_recording(encoder, 'videocapture1.h264')
time.sleep(6)

# It's better to capture the still in this thread, not in the one driving the camera.
request = picam2.capture_request()
request.save("main", "videocapture1.jpg")
request.release()
print("Still image captured!")

time.sleep(10)
picam2.stop_recording()
