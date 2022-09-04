#!/usr/bin/python3

# ImageServer used to stream photos from raspberry pi camera for liveview and high quality capture while maintaining the stream
#
# Set up script as a service to run always in the background:
# https://medium.com/codex/setup-a-python-script-as-a-service-through-systemctl-systemd-f0cc55a42267


# TODO / Improvements
# 1) cv2 face detection to autofocus on faces
# 2) add a way to change camera controls (sport mode, ...) to adapt for different lighting
# 3) improve autofocus algorithm
# 4) pause autofocus before HQ capture!
# 5) trigger for autofocus?
# 6) higher framerates! where is the bottleneck?

from io import BytesIO
import matplotlib.pyplot as plt
import argparse
import time
import cv2
from picamera2 import Picamera2, MappedArray
from urllib.parse import parse_qs
import logging
from picamera2 import Picamera2, MappedArray
from lib.FrameServer import FrameServer
from lib.Autofocus import FocusState, doFocus
# from lib.FocuserImx519 import Focuser      # import for Arducam 16mp sony imx519
from lib.FocuserImxArdu64 import Focuser    # import for Arducam 64mp
from lib.RepeatedTimer import RepeatedTimer
from http import server
import socketserver
from PIL import Image


# constants
class CONFIG:
    # debugging
    DEBUG_LOGFILE = False
    LOGGING_LEVEL = logging.DEBUG

    # quality
    MAIN_RESOLUTION_REDUCE_FACTOR = 2
    LORES_RESOLUTION = (1280, 720)
    LORES_QUALITY = 80
    HIRES_QUALITY = 90

    # autofocus
    # 70 for imx519 (range 0...4000) and 20 for arducam64mp (range 0...1000)
    FOCUS_STEP = 20

    # dont change following defaults. If necessary change via argument
    DEBUG = False
    DEBUG_SHOWPREVIEW = False
# constants


parser = argparse.ArgumentParser()

parser.add_argument('-v', '--verbose', action='store_true',
                    help="enable verbose debugging")
parser.add_argument('-p', '--preview', action='store_true',
                    help="enable local preview window")
args = parser.parse_args()

if args.verbose:
    CONFIG.DEBUG = True
if args.preview:
    CONFIG.DEBUG_SHOWPREVIEW = True


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
<title>Photobooth Imageserver</title>
</head>
<body>
<h1>Photobooth Imageserver</h1>
<form target="_blank" method="post" action="./capture"><input type="text" name="filename" value="test.jpeg"><input type="submit" value"take hq pic"></form>
<img src="stream.mjpg" height="720" /><br>
Last Focuser Run results
<img src="./images/focuser" id="image_focuser" /><br>

<script type="text/javascript">
const img = document.getElementById("image_focuser")

setInterval( () => {
   img.src = "./images/focuser#" + new Date().getTime();
}, 1000) // 1000ms
</script>
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
        elif self.path == '/images/focuser':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'image/png')
            self.end_headers()

            # create data
            print((focusState._lastRunResult))

            fig = plt.figure()
            ax = fig.add_subplot()
            fig.supxlabel('focus_absolute')
            fig.supylabel('sharpness')
            fig.suptitle('Sharpness(focus_absolute)')
            fig.tight_layout()

            ax.set_xlim(1, 1023)
            ax.grid(True)

            ax.plot(*zip(*focusState._lastRunResult))

            figdata = BytesIO()
            fig.savefig(figdata, format='png')

            self.wfile.write(figdata.getvalue())
        elif self.path == '/cmd/autofocus':
            self.send_response(200)
            self.end_headers()
            #TODO: dummy
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
    try:
        overlay1 = f"{focuser.get(focuser.OPT_FOCUS)} focus"
        overlay2 = f"{frameServer.fps} fps"
        overlay3 = f"Exposure time: {frameServer._metadata['ExposureTime']}us, resulting max fps: {round(1/frameServer._metadata['ExposureTime']*1000*1000,1)}"
        overlay4 = f"Lux: {round(frameServer._metadata['Lux'],1)}"
        overlay5 = f"Ae locked: {frameServer._metadata['AeLocked']}, analogue gain {frameServer._metadata['AnalogueGain']}"
        overlay6 = f"Colour Temp: {frameServer._metadata['ColourTemperature']}"
        colour = (210, 210, 210)
        origin1 = (10, 200)
        origin2 = (10, 230)
        origin3 = (10, 260)
        origin4 = (10, 290)
        origin5 = (10, 320)
        origin6 = (10, 350)
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1
        thickness = 2

        with MappedArray(request, "lores") as m:
            cv2.putText(m.array, overlay1, origin1,
                        font, scale, colour, thickness)
            cv2.putText(m.array, overlay2, origin2,
                        font, scale, colour, thickness)
            cv2.putText(m.array, overlay3, origin3,
                        font, scale, colour, thickness)
            cv2.putText(m.array, overlay4, origin4,
                        font, scale, colour, thickness)
            cv2.putText(m.array, overlay5, origin5,
                        font, scale, colour, thickness)
            cv2.putText(m.array, overlay6, origin6,
                        font, scale, colour, thickness)
    except:
        # fail silent if metadata still None (TODO: change None to Metadata contructor on init in Frameserver)
        pass


if __name__ == '__main__':
    picam2 = Picamera2()

    # print common information to log
    logger.info(f"sensor_modes: {picam2.sensor_modes}")

    main_resolution = [
        dim // CONFIG.MAIN_RESOLUTION_REDUCE_FACTOR for dim in picam2.sensor_resolution]
    main_stream = {"size": main_resolution}
    lores_stream = {"size": CONFIG.LORES_RESOLUTION}
    config = picam2.create_still_configuration(
        main_stream, lores_stream, encode="lores", buffer_count=1, display="lores")
    picam2.configure(config)

    logger.info(f"camera_config: {picam2.camera_config}")
    logger.info(f"camera_controls: {picam2.camera_controls}")
    logger.info(f"controls: {picam2.controls}")

    frameServer = FrameServer(picam2, logger, CONFIG)
    frameServer.start()

    focuser = Focuser("/dev/v4l-subdev1")
    focusState = FocusState()
    focuser.verbose = CONFIG.DEBUG
    focusState.verbose = CONFIG.DEBUG
    focusState.focus_step = CONFIG.FOCUS_STEP

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
