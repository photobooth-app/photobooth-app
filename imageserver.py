#!/usr/bin/python3

# ImageServer used to stream photos from raspberry pi camera for liveview and high quality capture while maintaining the stream
#
# Set up script as a service to run always in the background:
# https://medium.com/codex/setup-a-python-script-as-a-service-through-systemctl-systemd-f0cc55a42267


import time
import cv2
from picamera2 import Picamera2, MappedArray
from urllib.parse import parse_qs
import logging
from picamera2 import Picamera2, MappedArray
from lib.FrameServer import FrameServer
from lib.Autofocus import FocusState, doFocus
from lib.FocuserImx519 import Focuser519 as Focuser
from lib.RepeatedTimer import RepeatedTimer
from http import server
import socketserver
from PIL import Image


# constants
class CONFIG:
    # debugging
    DEBUG = False
    DEBUG_LOGFILE = False
    LOGGING_LEVEL = logging.INFO
    DEBUG_SHOWPREVIEW = False

    # quality
    MAIN_RESOLUTION_REDUCE_FACTOR = 1
    LORES_RESOLUTION = (1280, 720)
    LORES_QUALITY = 80
    HIRES_QUALITY = 90


# logger
print(CONFIG.LOGGING_LEVEL)
logger = logging.getLogger(__name__)
logger.setLevel(CONFIG.LOGGING_LEVEL)
fh = logging.StreamHandler()
fh_formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(lineno)d:%(filename)s(%(process)d) - %(message)s')
fh.setFormatter(fh_formatter)
logger.addHandler(fh)
if CONFIG.DEBUG_LOGFILE:
    fh2 = logging.FileHandler("/tmp/frameserver.log")
    fh2.setFormatter(fh_formatter)
    logger.addHandler(fh2)


thread_abort = False

PAGE = """\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<h1>Picamera2 MJPEG Streaming Demo</h1>
<img src="stream.mjpg" width="640" height="480" /><br>
<a href="./capture">trigger high quality capture</a>
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
            self.send_response(500)
            self.end_headers()

            self.wfile.write(b'use post command instead!\r\n')
        elif self.path == '/autofocus':
            self.send_response(200)
            self.end_headers()

            self.wfile.write(b'Done\r\n')
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
                logger.info(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/capture':
            start_time = time.time()

            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len)
            logger.debug("post_body(%s)" % (post_body))

            # decode -d "foo=bar" (application/x-www-form-urlencoded) sent by curl like:
            # curl -X POST -d 'filename=%s' http://localhost:8000/capture
            postvars = parse_qs(post_body.decode('utf-8'))
            logger.debug(f"post vars: {postvars}")

            # extract filename
            filename = postvars['filename'][0]
            logger.debug(f"save to file: {filename}")

            try:
                # triggerpic
                frameServer.trigger_hq_capture()

                # waitforpic and store to disk
                frame = frameServer.wait_for_hq_frame()
                PIL_image = Image.fromarray(frame.astype('uint8'), 'RGB')
                PIL_image.save(f"{filename}",
                               quality=CONFIG.HIRES_QUALITY)

                self.send_response(200)
                self.end_headers()
                processing_time = round((time.time() - start_time), 1)
                logger.info(
                    f"capture to file {filename} successfull, process took {processing_time}s")
                self.wfile.write(b'Done, frame capture successful\r\n')
            except Exception as e:
                logger.error(f"error during capture: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f'error during capture: {e}\r\n'.encode())
                self.wfile.write(b'error during capture\r\n')
            finally:
                pass
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def apply_overlay(request):
    overlay1 = f"{focuser.get(focuser.OPT_FOCUS)} focus"
    overlay2 = f"{frameServer.fps} fps"
    colour = (210, 210, 210)
    origin1 = (10, 200)
    origin2 = (10, 230)
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 1
    thickness = 2

    with MappedArray(request, "lores") as m:
        cv2.putText(m.array, overlay1, origin1,
                    font, scale, colour, thickness)
        cv2.putText(m.array, overlay2, origin2,
                    font, scale, colour, thickness)


if __name__ == '__main__':
    picam2 = Picamera2()

    main_resolution = [
        dim // CONFIG.MAIN_RESOLUTION_REDUCE_FACTOR for dim in picam2.sensor_resolution]
    main_stream = {"size": main_resolution}
    lores_stream = {"size": CONFIG.LORES_RESOLUTION}
    config = picam2.create_still_configuration(
        main_stream, lores_stream, encode="lores", buffer_count=1, display="lores")
    picam2.configure(config)

    frameServer = FrameServer(picam2, logger, CONFIG)
    frameServer.start()

    focuser = Focuser("/dev/v4l-subdev1")
    focusState = FocusState()
    focuser.verbose = CONFIG.DEBUG
    focusState.verbose = CONFIG.DEBUG

    if CONFIG.DEBUG:
        picam2.pre_callback = apply_overlay

    picam2.start(show_preview=CONFIG.DEBUG_SHOWPREVIEW)

    def refocus():
        logger.info("refocusing")

        doFocus(frameServer, focuser, focusState)

    # it auto-starts, no need of rt.start()
    refocus()
    rt = RepeatedTimer(5, refocus)

    # serve files forever
    try:
        address = ('', 8000)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        thread_abort = True
        rt.stop()  # better in a try/finally block to make sure the program ends!
        frameServer.stop()
        picam2.stop()

        logger.info(f"serverMain received {frameServer.count} frames")
