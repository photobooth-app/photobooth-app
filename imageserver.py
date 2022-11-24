#!/usr/bin/python3
from fastapi import Body, FastAPI
import shutil
import glob
import json
import signal
from queue import Queue
import uuid
import asyncio
from datetime import datetime
import piexif
from PIL import Image
import traceback
import sys
import time
import cv2
import logging
from lib.FrameServer import FrameServer
from lib.Autofocus import FocusState
# import for Arducam 16mp sony imx519
from lib.Focuser import Focuser
# from lib.FocuserImxArdu64 import Focuser    # import for Arducam 64mp
from lib.RepeatedTimer import RepeatedTimer
from lib.LocationService import LocationService
import os
from lib.InfoLed import InfoLed
from config import CONFIG
import uvicorn
from fastapi import FastAPI, Request, Body
from starlette.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from sse_starlette import EventSourceResponse, ServerSentEvent
import os
import threading
from pymitter import EventEmitter

"""
ImageServer used to stream photos from raspberry pi camera for liveview and high quality capture while maintaining the stream

# TODO / Improvements
1) idea: cv2 face detection to autofocus on faces (might be to high load on RP)
2) add a way to change camera controls (sport mode, ...) to adapt for different lighting
3) improve autofocus algorithm
4) check tuning file: https://github.com/raspberrypi/picamera2/blob/main/examples/tuning_file.py

"""

# change to files path
os.chdir(sys.path[0])


app = FastAPI()

ee = EventEmitter()

request_stop = False

# setup config object
config_instance = CONFIG()
config_instance.load()

# logger
logger = logging.getLogger(__name__)
logging.getLogger().handlers.clear()  # remove default handlers if any
logger.setLevel(config_instance.LOGGING_LEVEL)
fh = logging.StreamHandler()
fh_formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(lineno)d:%(filename)s(%(process)d) - %(message)s')
fh.setFormatter(fh_formatter)
logger.addHandler(fh)


def log_exceptions(type, value, tb):
    logger.exception(
        f"Uncaught exception: {str(value)} {(traceback.format_tb(tb))}")


# Install exception handler
sys.excepthook = log_exceptions

if config_instance.DEBUG_LOGFILE:
    fh2 = logging.FileHandler("/tmp/frameserver.log")
    fh2.setFormatter(fh_formatter)
    logger.addHandler(fh2)


def signal_handler(sig, frame):
    global request_stop

    request_stop = True

    logger.info("request_stop set True to stop ongoing processes")
    # TODO! this seems not to work properly yet, function is not called!

    # sys.exit(0)


# signal CTRL-C and systemctl stop
signal.signal(signal.SIGINT, signal_handler)


# rtQueue1 = RepeatedTimer(config_instance.FOCUSER_REPEAT_TRIGGER,
#                         ee.emit, event="publishSSE", sse_event="test", sse_data="data")


@app.get("/eventstream")
async def subscribe(request: Request):
    # principle with queues like described here:
    # https://maxhalford.github.io/blog/flask-sse-no-deps/
    # and https://github.com/sysid/sse-starlette
    # and https://github.com/encode/starlette/issues/20#issuecomment-587410233
    # ... this code example seems to be cleaner https://github.com/sysid/sse-starlette/blob/master/examples/custom_generator.py

    # local message queue
    queue = Queue()

    def add_subscriptions():
        logger.debug(f"add subscription for publishSSE")
        ee.on("publishSSE", addToQueue)

    def remove_subscriptions():
        logger.debug(f"remove subscriptions for publishSSE")
        ee.off("publishSSE", addToQueue)

    def addToQueue(sse_event, sse_data):
        logger.debug(f"addToQueue called event={sse_event} data={sse_data}")
        queue.put_nowait(ServerSentEvent(
            id=uuid.uuid4(), event=sse_event, data=sse_data, retry=10000))

    async def event_iterator():
        try:
            while True:
                if await request.is_disconnected():
                    logger.info(f"request.is_disconnected() true")
                    break
                if request_stop:
                    logger.info(f"event_iterator stop requested")
                    break

                try:
                    # try to get a event/message off the queue. timeout after 1 second to allow while loop break if client disconnected
                    # attention: queue.get(timeout=1) is blocking for 1sec - this blocks also other webserver threads!
                    # workaround is very small timeout
                    #event = queue.get(timeout=1)
                    event = queue.get(timeout=0.005)  # TODO optimize
                    # event = queue.get_nowait()  # not an option as this slows down the process (100% load for 1 cpu core)
                except:
                    continue

                # send data to client
                yield event

        except asyncio.CancelledError as e:
            logger.info(
                f"Disconnected from client (via refresh/close) {request.client}")
            # Do any other cleanup, if any
            remove_subscriptions()

            raise e

    logger.info(f"Client connected {request.client}")
    add_subscriptions()

    # initial messages on client connect
    addToQueue(sse_event="message",
               sse_data=f"Client connected {request.client}")
    addToQueue(sse_event="config/currentconfig",
               sse_data=json.dumps(config_instance.__dict__))  # TODO: needs to be changed to initial publish as all other.
    # all modules can register this event to send initial messages on connection

    ee.emit("publishSSE/initial")

    return EventSourceResponse(event_iterator(), ping=1)


@app.get("/debug/threads")
async def api_debug_threads():

    list = [item.getName() for item in threading.enumerate()]
    logger.debug(f"active threads: {list}")
    return (list)


@app.get("/cmd/{action}/{param}")
async def api_cmd(action, param):
    logger.info("log request")

    if (action == "debug"):
        config_instance.DEBUG = True if param == "on" else False
    elif (action == "debugoverlay"):
        config_instance.DEBUG_OVERLAY = True if param == "on" else False
    elif (action == "autofocus"):
        rt.start() if param == "on" else rt.stop()
    elif (action == "config"):
        if (param == "reset"):
            config_instance.reset_default_values()
        elif (param == "load"):
            config_instance.load()
        elif (param == "save"):
            config_instance.save()
        else:
            pass  # fail!
    elif (action == "exposuremode"):
        try:
            frameServer.setAeExposureMode(
                config_instance.CAPTURE_EXPOSURE_MODE)
        except:
            pass
        else:
            # save new val only if try succeeded
            config_instance.CAPTURE_EXPOSURE_MODE = param
    elif (action == "arm" and param == "countdown"):
        ee.emit("onCountdownTakePicture")

    return f"action={action}, param={param}"


@app.get("/cmd/capture")
@app.post("/cmd/capture")
def api_cmd_capture(filename: str = Body(f"{time.strftime('%Y%m%d_%H%M%S')}.jpg")):
    start_time = time.time()

    #logger.debug(f"request data={request}")

    # decode -d "foo=bar" (application/x-www-form-urlencoded) sent by curl like:
    # curl -X POST localhost:8000/cmd/capture -H 'accept: application/json' -H 'Content-Type: application/json' -d '"%s"'
    # filename = await request.json()  # ['filename']
    logger.debug(f"capture to filename: {filename}")

    try:
        # turn of autofocus trigger, cam needs to be in focus at this point by regular focusing
        rt.stop()

        # triggerpic
        frameServer.trigger_hq_capture()

        # waitforpic and store to disk
        frame = frameServer.wait_for_hq_frame()

        # grab metadata and store to exif
        now = datetime.now()
        zero_ifd = {piexif.ImageIFD.Make: "Arducam",
                    piexif.ImageIFD.Model: frameServer._picam2.camera.id,
                    piexif.ImageIFD.Software: "Photobooth Imageserver"}
        total_gain = frameServer._metadata["AnalogueGain"] * \
            frameServer._metadata["DigitalGain"]
        exif_ifd = {piexif.ExifIFD.ExposureTime: (frameServer._metadata["ExposureTime"], 1000000),
                    piexif.ExifIFD.DateTimeOriginal: now.strftime("%Y:%m:%d %H:%M:%S"),
                    piexif.ExifIFD.ISOSpeedRatings: int(total_gain * 100)}

        exif_dict = {"0th": zero_ifd, "Exif": exif_ifd}

        if (locationService.accuracy):
            logger.info("adding GPS data to exif")
            logger.debug(
                f"gps location: {locationService.latitude},{locationService.longitude}")

            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: locationService.latitudeRef,
                piexif.GPSIFD.GPSLatitude: locationService.latitudeDMS,
                piexif.GPSIFD.GPSLongitudeRef: locationService.longitudeRef,
                piexif.GPSIFD.GPSLongitude: locationService.longitudeDMS,
            }
            # add gps dict
            exif_dict.update({"GPS": gps_ifd})

        exif_bytes = piexif.dump(exif_dict)

        image = Image.fromarray(frame.astype('uint8'), 'RGB')
        image.save(f"{filename}",
                   quality=config_instance.HIRES_QUALITY, exif=exif_bytes)

        # later we have our own photobooth frontend - for now just copy to the development frontend for testing...
        shutil.copy2(filename, "data/images/")

        processing_time = round((time.time() - start_time), 1)
        logger.info(
            f"capture to file {filename} successfull, process took {processing_time}s")
        return (f'Done, frame capture successful')
    except Exception as e:
        logger.error(f"error during capture: {e}")

        return (f'error during capture: {e}')

    finally:
        # turn on regular autofocus in every case
        rt.start()


@app.get("/stats/focuser")
def api_stats_focuser():
    return (focusState._lastRunResult)


@app.get("/stats/locationservice")
def api_stats_locationservice():
    return (locationService._geolocation_response)


@app.get("/gallery/images")
def api_gallery_images():
    image_paths = sorted(glob.glob("data/images/*.jpg"),
                         key=os.path.getmtime, reverse=True)

    output = []
    for image_path in image_paths:
        output.append({
            "thumbnail": image_path,
            "image": image_path,
            "preview": image_path
        })
    return output


@app.get('')
@app.get('/')
def index():
    return app.send_static_file('index.html')


def gen_stream(frameServer):
    # get camera frame
    while True:
        if request_stop:
            break

        frame = frameServer.wait_for_lores_frame()

        is_success, buffer = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, config_instance.LORES_QUALITY])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n\r\n')


@app.get('/stream.mjpg')
def video_stream():
    return StreamingResponse(gen_stream(frameServer),
                             media_type='multipart/x-mixed-replace; boundary=frame')


# serve data directory holding images, thumbnails, ...
app.mount('/data', StaticFiles(directory='data'), name="data")

# if not match anything above, default to deliver static files from web directory
app.mount("/", StaticFiles(directory="web"), name="web")


if __name__ == '__main__':
    infoled = InfoLed(config_instance, ee)
    frameServer = FrameServer(logger, ee, config_instance)
    focuser = Focuser(config_instance.FOCUSER_DEVICE, config_instance)
    focusState = FocusState(frameServer, focuser, ee, config_instance)
    rt = RepeatedTimer(config_instance.FOCUSER_REPEAT_TRIGGER,
                       ee.emit, "onRefocus")
    locationService = LocationService(logger, ee, config_instance)

    frameServer.start()

    focuser.reset()

    # first time focus
    ee.emit("onRefocus")

    # first time try to get location
    locationService.start()

    # log all registered listener
    logger.debug(ee.listeners_all())

    # serve files forever
    try:
        # log_level="trace", default info
        uvicorn.run(app, host="0.0.0.0", port=8000,
                    log_level="info")
    finally:
        rt.stop()  # better in a try/finally block to make sure the program ends!
        frameServer.stop()
