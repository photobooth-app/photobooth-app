#!/usr/bin/python3

from lib.Exif import Exif
import os
from lib.ImageDb import ImageDb
from turbojpeg import TurboJPEG
import psutil
from gpiozero import CPUTemperature, LoadAverage
from pymitter import EventEmitter
import threading
from sse_starlette import EventSourceResponse, ServerSentEvent
from fastapi.responses import StreamingResponse, FileResponse
from starlette.staticfiles import StaticFiles
from fastapi import FastAPI, Request, Body, HTTPException
import uvicorn
from lib.InfoLed import InfoLed
from lib.LocationService import LocationService
from lib.RepeatedTimer import RepeatedTimer
from lib.Focuser import Focuser
from lib.Autofocus import FocusState
from lib.FrameServer import FrameServer
import time
import asyncio
import uuid
from queue import Queue
import signal
import json
import shutil
from lib.ConfigService import ConfigService
import logging

# create early instances
# event system
ee = EventEmitter()
# setup config object
cs = ConfigService(ee)

# setup logger


class EventstreamLogHandler(logging.Handler):
    """
    Logging handler to emit events to eventstream; to be displayed in console.log on browser frontend
    """

    def __init__(self):
        logging.Handler.__init__(self)

    def emit(self, record):
        ee.emit("publishSSE", sse_event="message",
                sse_data=self.format(record))


logging.config.dictConfig(cs._internal_config["LOGGING_CONFIG"])

# setup configservice
cs.load()
# print(cs._current_config)

# reconfigure if any changes from config needs to be applied.
logging.config.dictConfig(cs._internal_config["LOGGING_CONFIG"])


logger = logging.getLogger(__name__)
logger.info('Welcome to qPhotobooth')

"""
ImageServer used to stream photos from raspberry pi camera for liveview and high quality capture while maintaining the stream

# TODO / Improvements
1) idea: cv2 face detection to autofocus on faces (might be to high load on RP)
2) add a way to change camera controls (sport mode, ...) to adapt for different lighting
3) improve autofocus algorithm
4) check tuning file: https://github.com/raspberrypi/picamera2/blob/main/examples/tuning_file.py

"""

app = FastAPI()


request_stop = False


def signal_handler(sig, frame):
    global request_stop

    request_stop = True

    logger.info("request_stop set True to stop ongoing processes")
    # TODO! this seems not to work properly yet, function is not called!

    # sys.exit(0)


# signal CTRL-C and systemctl stop
signal.signal(signal.SIGINT, signal_handler)


@app.get("/eventstream")
async def subscribe(request: Request):
    # principle with queues like described here:
    # https://maxhalford.github.io/blog/flask-sse-no-deps/
    # and https://github.com/sysid/sse-starlette
    # and https://github.com/encode/starlette/issues/20#issuecomment-587410233
    # ... this code example seems to be cleaner https://github.com/sysid/sse-starlette/blob/master/examples/custom_generator.py

    # local message queue
    queue = Queue()  # TODO: limit max queue size in case client doesnt catch up so fast?

    def add_subscriptions():
        logger.debug(f"add subscription for publishSSE")
        ee.on("publishSSE", addToQueue)

    def remove_subscriptions():
        logger.debug(f"remove subscriptions for publishSSE")
        ee.off("publishSSE", addToQueue)

    def addToQueue(sse_event, sse_data):
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
               sse_data=json.dumps(cs._current_config))  # TODO: needs to be changed to initial publish as all other.

    # all modules can register this event to send initial messages on connection
    ee.emit("publishSSE/initial")

    return EventSourceResponse(event_iterator(), ping=1)


@app.get("/debug/health")
async def api_debug_health():
    la = LoadAverage(
        minutes=1, max_load_average=psutil.cpu_count(), threshold=psutil.cpu_count()*0.8)
    cpu_temperature = round(CPUTemperature().temperature, 1)
    return ({"cpu_current_load": la.value, "cpu_above_threshold": la.is_active, "cpu_temperature": cpu_temperature})


@app.get("/debug/threads")
async def api_debug_threads():

    list = [item.getName() for item in threading.enumerate()]
    logger.debug(f"active threads: {list}")
    return (list)


@app.get("/config/current")
async def api_get_config_current():
    return (cs._current_config)


@app.post("/config/current")
async def api_post_config_current(request: Request):
    sent_config_json = await request.json()
    cs.import_config(sent_config_json)
    cs.save()


@app.get("/cmd/{action}/{param}")
async def api_cmd(action, param):
    logger.info(f"cmd api requested action={action}, param={param}")

    if (action == "config"):
        if (param == "reset"):
            cs.reset_default_values()
        elif (param == "load"):
            cs.load()
        elif (param == "save"):
            cs.save()
        else:
            pass  # fail!
    elif (action == "arm" and param == "countdown"):
        ee.emit("onCountdownTakePicture")
    elif (action == "server" and param == "reboot"):
        os.system("reboot")
    elif (action == "server" and param == "shutdown"):
        os.system("shutdown now")
    else:
        raise HTTPException(
            500, f"invalid request action={action}, param={param}")

    return f"action={action}, param={param}"


@app.get("/cmd/capture")
def api_cmd_capture_get():
    return capture(f"{time.strftime('%Y%m%d_%H%M%S')}.jpg")


@app.post("/cmd/capture")
def api_cmd_capture_post(filepath: str = Body("capture.jpg")):
    return capture(filepath, True)


def capture(requested_filepath, copyForCompatibility=False):

    start_time = time.time()

    if not requested_filepath:
        requested_filepath = f"{time.strftime('%Y%m%d_%H%M%S')}.jpg"

    #logger.debug(f"request data={request}")

    # decode -d "foo=bar" (application/x-www-form-urlencoded) sent by curl like:
    # curl -X POST localhost:8000/cmd/capture -H 'accept: application/json' -H 'Content-Type: application/json' -d '"%s"'
    # filename = await request.json()  # ['filename']
    logger.debug(f"capture to filename: {requested_filepath}")

    try:
        # turn of autofocus trigger, cam needs to be in focus at this point by regular focusing
        rt.stop()

        jpeg = TurboJPEG()

        # triggerpic
        frameServer.trigger_hq_capture()

        # waitforpic and store to disk
        frame = frameServer.wait_for_hq_frame()

        # create JPGs and add to db
        (item, id) = imageDb.createImageSetFromFrame(frame, requested_filepath)
        actual_filepath = item['image']

        # add exif information
        if cs._current_config["PROCESS_ADD_EXIF_DATA"]:
            logger.info("add exif data to image")
            try:
                exif.injectExifToJpeg(actual_filepath)
            except Exception as e:
                logger.exception(
                    f"something went wrong injecting the exif: {e}")

        # also create a copy for photobooth compatibility
        if copyForCompatibility:
            # photobooth sends a complete path, where to put the file, so copy it to requested filepath
            shutil.copy2(actual_filepath, requested_filepath)

        processing_time = round((time.time() - start_time), 1)
        logger.info(
            f"capture to file {actual_filepath} successfull, process took {processing_time}s")
        return (f'Done, frame capture successful')
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=500, detail=f"error during capture: {e}")

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
    try:
        return imageDb.dbGetImages()
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=500, detail=f"something went wrong, Exception: {e}")


@app.get("/gallery/delete")
def api_gallery_delete(id: str):
    logger.info(f"gallery_delete requested, id={id}")
    try:
        imageDb.deleteImage(id)
        return "OK"
    except Exception as e:
        logger.exception(e)
        # print(e)
        raise HTTPException(500, f"deleting failed: {e}")


def gen_stream(frameServer):
    skip_counter = cs._current_config["PREVIEW_PREVIEW_FRAMERATE_DIVIDER"]
    jpeg = TurboJPEG()

    while True:
        if request_stop:
            break

        frame = frameServer.wait_for_lores_frame()

        if (skip_counter <= 1):
            buffer = jpeg.encode(
                frame, quality=cs._current_config["LORES_QUALITY"])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer + b'\r\n\r\n')
            skip_counter = cs._current_config["PREVIEW_PREVIEW_FRAMERATE_DIVIDER"]
        else:
            skip_counter -= 1


@app.get('/stream.mjpg')
def video_stream():
    return StreamingResponse(gen_stream(frameServer),
                             media_type='multipart/x-mixed-replace; boundary=frame')


# serve data directory holding images, thumbnails, ...
app.mount('/data', StaticFiles(directory='data'), name="data")


@app.get("/")
async def read_index():
    return FileResponse('web/index.html')

# if not match anything above, default to deliver static files from web directory
app.mount("/", StaticFiles(directory="web"), name="web")

if __name__ == '__main__':
    infoled = InfoLed(cs, ee)
    frameServer = FrameServer(ee, cs)
    imageDb = ImageDb(cs, frameServer)
    focuser = Focuser(cs._current_config["FOCUSER_DEVICE"], cs)
    focusState = FocusState(frameServer, focuser, ee, cs)
    rt = RepeatedTimer(cs._current_config["FOCUSER_REPEAT_TRIGGER"],
                       ee.emit, "onRefocus")
    locationService = LocationService(ee, cs)
    exif = Exif(cs, frameServer, locationService)

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
