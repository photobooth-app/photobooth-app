#!/usr/bin/python3

# Mostly copied from https://picamera.readthedocs.io/en/release-1.13/recipes2.html
# Run this script, then point a web browser at http:<this-ip-address>:8000
# Note: needs simplejpeg to be installed (pip3 install simplejpeg).

import threading
import io
import logging
import socketserver
from http import server
from threading import Condition
import cv2

from picamera2 import Picamera2, MappedArray
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

#from lib.RpiCamera import Camera
from lib.Focuser519 import Focuser519 as Focuser
from lib.AutofocusCallback import FocusState, doFocus

exit_ = False


def sigint_handler(signum, frame):
    global exit_
    exit_ = True


#signal.signal(signal.SIGINT, sigint_handler)
#signal.signal(signal.SIGTERM, sigint_handler)

PAGE = """\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<h1>Picamera2 MJPEG Streaming Demo</h1>
<img src="stream.mjpg" width="640" height="480" />
</body>
</html>
"""


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header(
                'Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


picam2 = Picamera2()
half_resolution = [dim // 2 for dim in picam2.sensor_resolution]
main_stream = {"size": picam2.sensor_resolution, 'format': 'XRGB8888'}
lores_stream = {"size": (640, 480), 'format': 'YUV420'}
video_config = picam2.create_still_configuration(
    main_stream, lores_stream, encode="lores")
picam2.configure(video_config)

output = StreamingOutput()

colour = (0, 255, 0)
origin = (0, 30)
font = cv2.FONT_HERSHEY_SIMPLEX
scale = 1
thickness = 2


def apply_timestamp(request):
    timestamp = str(focuser.get(focuser.OPT_FOCUS))
    with MappedArray(request, "main") as m:
        cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness)
    #os.system("v4l2-ctl -c focus_absolute=%d -d /dev/v4l-subdev1" % (500))


picam2.pre_callback = apply_timestamp

picam2.start_recording(JpegEncoder(colour_space='YUV420',
                       colour_subsampling='420'), FileOutput(output))


focuser = Focuser("/dev/v4l-subdev1")
focuser.verbose = True
focusState = FocusState()
focusState.verbose = True


def setInterval(interval):
    def decorator(function):
        def wrapper(*args, **kwargs):
            stopped = threading.Event()

            def loop():  # executed in another thread
                while not stopped.wait(interval):  # until stopped
                    function(*args, **kwargs)

            t = threading.Thread(target=loop)
            t.daemon = True  # stop if the program exits
            t.start()
            return stopped
        return wrapper
    return decorator


# @setInterval(5)
def refocus():
    print("refocusing\n")

    # if focusState.isFinish():
    doFocus(picam2, focuser, focusState)


# refocus()


@setInterval(5)
def capture():
    print("capturing\n")

    request = picam2.capture_request()
    request.save("main", "StreamMjpgStill.jpg")
    print(request.get_metadata())
    request.release()
    print("Still image captured!")


capture()

try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    server.shutdown()

print("Exit Program\n")
