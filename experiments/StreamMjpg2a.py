# https://lightrun.com/answers/raspberrypi-picamera2-how-to-simultaneous-recording-and-webserver


#import logging
import socketserver
from http import server
from threading import Condition, Thread
import simplejpeg
import cv2
import threading
from picamera2 import Picamera2
import time
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


def mjpeg_encode():
    global mjpeg_frame
    while not mjpeg_abort:
        yuv = picam2.capture_array("lores")
        rgb = cv2.cvtColor(yuv, cv2.COLOR_YUV420p2RGB)
        buf = simplejpeg.encode_jpeg(
            rgb, quality=80, colorspace='BGR', colorsubsampling='420')
        with mjpeg_condition:
            mjpeg_frame = buf
            mjpeg_condition.notify_all()


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
                    with mjpeg_condition:
                        mjpeg_condition.wait()
                        frame = mjpeg_frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                print(
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
main_stream = {"size": half_resolution}
lores_stream = {"size": (640, 480)}
video_config = picam2.create_still_configuration(
    main_stream, lores_stream, encode="lores")
picam2.configure(video_config)

picam2.start()

mjpeg_abort = False
mjpeg_frame = None
mjpeg_condition = Condition()
mjpeg_thread = Thread(target=mjpeg_encode, daemon=True)
mjpeg_thread.start()


def capture():
    print("capturing\n")

    mjpeg_abort = True
    time.sleep(1)
    print("capturing\n")
    request = picam2.capture_request()
    request.save("main", "StreamMjpgStill2a.jpg")
    print(request.get_metadata())
    request.release()
    time.sleep(1)
    mjpeg_abort = False
    print("Still image captured!")


S = threading.Timer(5.0, capture)
S.start()
# capture()

try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    mjpeg_abort = True
    mjpeg_thread.join()
