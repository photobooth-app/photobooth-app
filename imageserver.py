#!/usr/bin/python3
import uuid
import asyncio
from datetime import datetime
import piexif
from PIL import Image
import traceback
from EventNotifier import Notifier
import sys
import time
import cv2
import logging
from picamera2 import Picamera2
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
from fastapi import FastAPI, Form, Request
from starlette.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import os
import threading
import json

"""
ImageServer used to stream photos from raspberry pi camera for liveview and high quality capture while maintaining the stream

# TODO / Improvements
event system: EventNotifier vs Pyee vs this list: https://stackoverflow.com/a/16192256
thinking about using blinker or pymitter


1) idea: cv2 face detection to autofocus on faces (might be to high load on RP)
2) add a way to change camera controls (sport mode, ...) to adapt for different lighting
3) improve autofocus algorithm
4) check tuning file: https://github.com/raspberrypi/picamera2/blob/main/examples/tuning_file.py

"""


# change to files path
os.chdir(sys.path[0])


app = FastAPI()


# setup config object
config_instance = CONFIG()
config_instance.load()

# logger
logger = logging.getLogger(__name__)
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

notifier = Notifier(
    ["onTakePicture", "onTakePictureFinished", "onCountdownTakePicture", "onRefocus"], logger)


@app.get('/eventstream')
async def message_stream(request: Request):
    def new_messages():
        # Add logic here to check for new messages
        yield 'Hello World'

    async def event_generator():
        while True:
            # If client closes connection, stop sending events
            if await request.is_disconnected():
                break

            # Checks for new messages and return them to client if any
            if new_messages():
                yield {
                    "event": "message",
                    "id": uuid.uuid4(),
                    "retry": 15000,
                    "data": "message_content"
                }
                yield {
                    "event": "stats/focuser",
                    "id": uuid.uuid4(),
                    "retry": 15000,
                    "data": json.dumps({"key1": "value1", "key2": "value2"})
                }
                yield {
                    "event": "stats/geolocation",
                    "id": uuid.uuid4(),
                    "retry": 15000,
                    "data": json.dumps((locationService._geolocation_response))
                }

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


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
        notifier.raise_event("onCountdownTakePicture")

    return f"action={action}, param={param}"


@app.post("/cmd/capture")
def api_cmd_capture(filename: str = Form()):
    start_time = time.time()

    #logger.debug(f"request data={request}")

    # decode -d "foo=bar" (application/x-www-form-urlencoded) sent by curl like:
    # curl -X POST -d 'filename=%s' http://localhost:8000/cmd/capture
    #filename = request.form['filename']
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
                    piexif.ImageIFD.Model: picam2.camera.id,
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


@app.get('/')
def index():
    return app.send_static_file('index.html')


def gen_stream(frameServer):
    # get camera frame
    while True:
        frame = frameServer.wait_for_lores_frame()

        is_success, buffer = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, config_instance.LORES_QUALITY])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n\r\n')


@app.get('/stream.mjpg')
def video_stream():
    return StreamingResponse(gen_stream(frameServer),
                             media_type='multipart/x-mixed-replace; boundary=frame')


# if not match anything above, default to deliver static files from web directory
app.mount("/", StaticFiles(directory="web"), name="web")

if __name__ == '__main__':
    picam2 = Picamera2()
    infoled = InfoLed(config_instance, notifier)
    frameServer = FrameServer(picam2, logger, notifier, config_instance)
    focuser = Focuser(config_instance.FOCUSER_DEVICE, config_instance)
    focusState = FocusState(frameServer, focuser, notifier, config_instance)
    rt = RepeatedTimer(config_instance.FOCUSER_REPEAT_TRIGGER,
                       notifier.raise_event, "onRefocus")
    locationService = LocationService(logger, notifier, config_instance)

    frameServer.start()

    focuser.reset()

    # first time focus
    notifier.raise_event("onRefocus")

    # first time try to get location
    locationService.start()

    # serve files forever
    try:
        #app.run(host='0.0.0.0', port=8000)
        # uvicorn.run("fastapi_code:app")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        rt.stop()  # better in a try/finally block to make sure the program ends!
        frameServer.stop()
        picam2.stop()
