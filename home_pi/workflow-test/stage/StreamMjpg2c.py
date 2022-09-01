# https://lightrun.com/answers/raspberrypi-picamera2-how-to-simultaneous-recording-and-webserver


# idea working :)


#import logging
import socketserver
from http import server
from threading import Condition, Thread
import simplejpeg
import cv2
import time
import threading
from picamera2 import Picamera2, MappedArray
from lib.Focuser519 import Focuser519 as Focuser
from lib.AutofocusCallback import FocusState

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


def pic_capture():
    global capture_pic
    global mjpeg_conversion_flag

    while True:
        if capture_pic:
            mjpeg_conversion_flag = False
            time.sleep(0.4)
            print("capturing 1 sec delay\n")
            request = picam2.capture_request()
            request.save("main", "StreamMjpgStill2b.jpg")
            print(request.get_metadata())
            request.release()
            time.sleep(0.1)
            capture_pic = False
            mjpeg_conversion_flag = True


def mjpeg_conversion():
    global mjpeg_frame

    while True:
        if mjpeg_conversion_flag:
            yuv = picam2.capture_array("lores")
            rgb = cv2.cvtColor(yuv, cv2.COLOR_YUV420p2RGB)
            buf = simplejpeg.encode_jpeg(
                rgb, quality=90, colorspace='BGR', colorsubsampling='420')
            size = len(buf)
            print("jpeg size", round(size/1000, 1))
            with mjpeg_condition:
                mjpeg_frame = buf
                mjpeg_condition.notify_all()

            print('mjpeg conversion active')


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        global capture_pic
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
        elif self.path == '/capture':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            capture_pic = True
            self.end_headers()

            while capture_pic:
                time.sleep(0.05)

            self.wfile.write(b'frame capture done\r\n')
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
main_stream = {"size": picam2.sensor_resolution}
lores_stream = {"size": (640, 480)}
video_config = picam2.create_still_configuration(
    main_stream, lores_stream, encode="lores")
picam2.configure(video_config)


colour = (0, 255, 0)
origin = (0, 30)
font = cv2.FONT_HERSHEY_SIMPLEX
scale = 1
thickness = 2


def apply_timestamp(request):
    timestamp = str(focuser.get(focuser.OPT_FOCUS))
    with MappedArray(request, "lores") as m:
        cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness)
    #os.system("v4l2-ctl -c focus_absolute=%d -d /dev/v4l-subdev1" % (500))


picam2.pre_callback = apply_timestamp

picam2.start()

focuser = Focuser("/dev/v4l-subdev1")
focuser.verbose = True
focusState = FocusState()
focusState.verbose = True

mjpeg_conversion_flag = True
capture_pic = False
mjpeg_frame = None
mjpeg_condition = Condition()
mjpeg_thread = Thread(target=mjpeg_conversion, daemon=True)
mjpeg_thread.start()
pic_condition = Condition()
pic_thread = Thread(target=pic_capture, daemon=True)
pic_thread.start()


def capture():
    print("capturing\n")
    global capture_pic
    capture_pic = True


S = threading.Timer(5.0, capture)
S.start()
# capture()


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


@setInterval(5)
def refocus():
    print("refocusing\n")

    focusState.reset()  # fix: reset because otherwise focusthread will not loop
    #doFocus(picam2, focuser, focusState)


# refocus()


statsThread_ = threading.Thread(
    target=statsThread, args=(camera, focuser, focusState))
statsThread_.daemon = True
statsThread_.start()

focusThread_ = threading.Thread(
    target=focusThread, args=(focuser, focusState))
focusThread_.daemon = True
focusThread_.start()


try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    mjpeg_conversion_flag = False
    mjpeg_thread.join()
