#!/usr/bin/python3

from threading import Timer
from lib.AutofocusCallbackFrameserver import FocusState, doFocus
from lib.Focuser519 import Focuser519 as Focuser
import time
import cv2
import simplejpeg
from threading import Condition, Thread

from http import server
import socketserver
from PIL import Image
from picamera2 import Picamera2, MappedArray
import simplejson


DEBUG = True
LORES_QUALITY = 85
HIRES_QUALITY = 85


class FrameServer:
    def __init__(self, picam2):
        """A simple class that can serve up frames from one of the Picamera2's configured
        streams to multiple other threads.
        Pass in the Picamera2 object and the name of the stream for which you want
        to serve up frames."""
        self._picam2 = picam2
        self._hq_array = None
        self._lores_array = None
        self._lores_convert_to_jpeg = True
        self._hq_condition = Condition()
        self._lores_condition = Condition()
        self._trigger_hq_capture = False
        self._running = True
        self._count = 0
        self._thread = Thread(target=self._thread_func, daemon=True)

    @property
    def count(self):
        """A count of the number of frames received."""
        return self._count

    def start(self):
        """To start the FrameServer, you will also need to start the Picamera2 object."""
        self._thread.start()

    def stop(self):
        """To stop the FrameServer, first stop any client threads (that might be
        blocked in wait_for_frame), then call this stop method. Don't stop the
        Picamera2 object until the FrameServer has been stopped."""
        self._running = False
        self._thread.join(1)

    def trigger_hq_capture(self):
        """switch one time to hq capture"""
        self._trigger_hq_capture = True

    def _thread_func(self):
        while self._running:

            # to calc frames per second
            start_time = time.time()  # start time of the loop

            if not self._trigger_hq_capture:
                array = picam2.capture_array("lores")

                if self._lores_convert_to_jpeg:
                    rgb = cv2.cvtColor(array, cv2.COLOR_YUV420p2RGB)
                    buf = simplejpeg.encode_jpeg(
                        rgb, quality=LORES_QUALITY, colorspace='BGR', colorsubsampling='420')
                    size = len(buf)
                    print('mjpeg conversion active', "jpeg size: ",
                          round(size/1000, 1), "kb")

                    array = buf

                with self._lores_condition:
                    self._lores_array = array
                    self._lores_condition.notify_all()
            else:
                # only capture one pic and return to lores streaming afterwards
                self._trigger_hq_capture = False

                # capture hq picture
                array = self._picam2.capture_array("main")
                with self._hq_condition:
                    self._hq_array = array
                    self._hq_condition.notify_all()

            # FPS = 1 / time to process loop
            if DEBUG:
                print("FPS: ", 1.0 / (time.time() - start_time))

            self._count += 1

    def wait_for_lores_frame(self):
        """for other threads to receive a lores frame"""
        with self._lores_condition:
            while True:
                self._lores_condition.wait()
                return self._lores_array

    def wait_for_hq_frame(self):
        """for other threads to receive a hq frame"""
        with self._hq_condition:
            while True:
                self._hq_condition.wait()
                return self._hq_array


# Below here is just demo code that uses the class:

def thread1_func():
    global thread1_count
    while not thread_abort:
        frame = frameServer.wait_for_hq_frame()
        # unused actually - remove...

        thread1_count += 1


def thread2_func():
    global thread2_count
    frame = None
    while not thread_abort:
        frame = frameServer.wait_for_lores_frame()
        # unused actually - remove...
        thread2_count += 1


thread_abort = False
thread1_count = 0
thread2_count = 0
thread1 = Thread(target=thread1_func, daemon=True)
thread2 = Thread(target=thread2_func, daemon=True)

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
        elif self.path == '/capture':
            self.send_response(200)
            self.end_headers()

            # triggerpic
            frameServer.trigger_hq_capture()

            # waitforpic and store to disk
            frame = frameServer.wait_for_hq_frame()
            PIL_image = Image.fromarray(frame.astype('uint8'), 'RGB')
            PIL_image.save("frame_server2mjpgHQoverlSrv.jpeg",
                           quality=HIRES_QUALITY)

            self.wfile.write(b'frame capture successful\r\n')
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
                    frame = frameServer.wait_for_lores_frame()

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

    def do_POST(self):
        if self.path == '/capture':
            print("got post!!")
            content_len = int(self.headers.getheader('content-length', 0))
            post_body = self.rfile.read(content_len)
            test_data = simplejson.loads(post_body)
            print("post_body(%s)" % (test_data))

            # triggerpic
            frameServer.trigger_hq_capture()

            # waitforpic and store to disk
            frame = frameServer.wait_for_hq_frame()
            PIL_image = Image.fromarray(frame.astype('uint8'), 'RGB')
            PIL_image.save("frame_server2mjpgHQoverlSrv.jpeg",
                           quality=HIRES_QUALITY)

            self.send_response(200)
            self.wfile.write(b'frame capture successful\r\n')
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


picam2 = Picamera2()
full_resolution = picam2.sensor_resolution
half_resolution = [dim // 2 for dim in picam2.sensor_resolution]
main_stream = {"size": full_resolution}
lores_stream = {"size": (640, 480)}
config = picam2.create_still_configuration(
    main_stream, lores_stream, encode="lores", buffer_count=1, display="lores")
picam2.configure(config)
frameServer = FrameServer(picam2)
thread1.start()
thread2.start()
frameServer.start()

focuser = Focuser("/dev/v4l-subdev1")
focuser.verbose = True
focusState = FocusState()
focusState.verbose = True


def apply_overlay(request):
    overlay1 = str(focuser.get(focuser.OPT_FOCUS))
    colour = (0, 255, 0)
    origin = (0, 30)
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 1
    thickness = 2

    with MappedArray(request, "lores") as m:
        cv2.putText(m.array, overlay1, origin, font, scale, colour, thickness)


if DEBUG:
    picam2.pre_callback = apply_overlay

picam2.start(show_preview=DEBUG)

if DEBUG:
    time.sleep(1)
    doFocus(frameServer, focuser, focusState)


class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False


def refocus():
    print("refocusing\n")

    # focusState.reset()  # fix: reset because otherwise focusthread will not loop
    doFocus(frameServer, focuser, focusState)


# it auto-starts, no need of rt.start()
rt = RepeatedTimer(5, refocus)


if DEBUG:
    time.sleep(1)
    frameServer.trigger_hq_capture()

try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    thread_abort = True
    rt.stop()  # better in a try/finally block to make sure the program ends!
    thread1.join(timeout=1)
    thread2.join(timeout=1)
    frameServer.stop()
    picam2.stop()

    print("Thread1 received", thread1_count, "frames")
    print("Thread2 received", thread2_count, "frames")
    print("serverMain received", frameServer.count, "frames")
