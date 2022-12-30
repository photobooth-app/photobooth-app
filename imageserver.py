#!/usr/bin/python3
from lib.LoggingService import EventstreamLogHandler
from importlib import import_module
from lib.ConfigSettings import ConfigSettings, settings
from lib.KeyboardService import KeyboardService
from lib.CamStateMachine import TakePictureMachineModel, states, transitions
from transitions import Machine
from lib.Exif import Exif
import os
from lib.ImageDb import ImageDb
import psutil
from gpiozero import CPUTemperature, LoadAverage
from pymitter import EventEmitter
import threading
from sse_starlette import EventSourceResponse, ServerSentEvent
from fastapi.responses import StreamingResponse, FileResponse
from starlette.staticfiles import StaticFiles
from fastapi import FastAPI, Request, HTTPException, status, Body
import uvicorn
from lib.InfoLed import InfoLed
from lib.LocationService import LocationService
import asyncio
import uuid
from queue import Queue
import logging
from lib.LoggingService import LoggingService
import platform


# create early instances
# event system
ee: EventEmitter = EventEmitter()
ls: LoggingService = LoggingService(ee=ee)

# constants
SERVICE_NAME = "imageserver"


logger = logging.getLogger(__name__)
logger.info('Welcome to qPhotobooth')
logger.info(f"platform.system={platform.system()}")
logger.info(f"platform.release={platform.release()}")
logger.info(f"platform.machine={platform.machine()}")
logger.info(f"platform.python_version={platform.python_version()}")
logger.info(f"hostname={platform.node()}")
logger.info(f"psutil.cpu_count logical={psutil.cpu_count()}")
logger.info(f"psutil.cpu_count cores={psutil.cpu_count(logical=False)}")
logger.info(f"psutil.disk_partitions={psutil.disk_partitions()}")
if platform.system() == "Linux":
    logger.info(f"psutil.disk_usage /={psutil.disk_usage('/')}")
elif platform.system() == "Windows":
    logger.info(f"psutil.disk_usage C:={psutil.disk_usage('C:')}")
logger.info(f"psutil.net_if_addrs={psutil.net_if_addrs()}")
logger.info(f"psutil.net_if_addrs={psutil.net_if_addrs()}")
logger.info(f"psutil.virtual_memory={psutil.virtual_memory()}")
# run python with -O (optimized) sets debug to false and disables asserts from bytecode
logger.info(f"__debug__={__debug__}")


app = FastAPI()

"""
request_stop = False


def signal_handler(sig, frame):
    global request_stop

    request_stop = True

    logger.info("request_stop set True to stop ongoing processes")
    # TODO! this seems not to work properly yet, function is not called!

    # sys.exit(0)


# signal CTRL-C and systemctl stop
signal.signal(signal.SIGINT, signal_handler)
# this is not working, because uvicorn is eating up signal handler definitions currently: https://github.com/encode/uvicorn/issues/1579
# as workaround currently we set force_exit to True to shutdown the server
"""


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
                # if request_stop:
                #    logger.info(f"event_iterator stop requested")
                #    break

                try:
                    # try to get a event/message off the queue. timeout after 1 second to allow while loop break if client disconnected
                    # attention: queue.get(timeout=1) is blocking for 1sec - this blocks also other webserver threads!
                    # workaround is very small timeout
                    # event = queue.get(timeout=1)
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
               sse_data=settings.json())

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


@app.get("/config/schema")
async def api_get_config_schema():
    return (settings.schema())


@app.get("/config/current")
async def api_get_config_current():
    return (settings.dict())


@app.post("/config/current")
async def api_post_config_current(updatedSettings: ConfigSettings):
    updatedSettings.persist()  # save settings to disc
    # restart service to load new config

    status = os.system(f'systemctl is-active --quiet {SERVICE_NAME}')
    # will return 0 for active else inactive.

    if (status == 0):
        logger.info(f"service {SERVICE_NAME} currently active, restarting")
        os.system(f"systemctl restart {SERVICE_NAME}")
    else:
        logger.warning(
            f"service {SERVICE_NAME} currently inactive, need to restart by yourself!")


@app.get("/cmd/frameserver/capturemode", status_code=status.HTTP_204_NO_CONTENT)
# photobooth compatibility
def api_cmd_framserver_capturemode_get():
    ee.emit("onCaptureMode")


@app.get("/cmd/frameserver/previewmode", status_code=status.HTTP_204_NO_CONTENT)
# photobooth compatibility
def api_cmd_frameserver_previewmode_get():
    ee.emit("onPreviewMode")


@app.post("/cmd/capture", status_code=status.HTTP_200_OK)
# photobooth compatibility
def api_cmd_capture_post(filepath: str = Body("capture.jpg")):
    return imageDb.captureHqImage(filepath, True)


@app.get("/cmd/{action}/{param}")
async def api_cmd(action, param):
    logger.info(f"cmd api requested action={action}, param={param}")

    if (action == "config" and param == "reset"):
        settings.deleteconfig()
    elif (action == "server" and param == "reboot"):
        os.system("reboot")
    elif (action == "server" and param == "shutdown"):
        os.system("shutdown now")
    elif (action == "service" and param == "restart"):
        os.system("systemctl restart imageserver")
    elif (action == "service" and param == "stop"):
        os.system("systemctl stop imageserver")
    elif (action == "service" and param == "start"):
        os.system("systemctl start imageserver")

    else:
        raise HTTPException(
            500, f"invalid request action={action}, param={param}")

    return f"action={action}, param={param}"


"""
CAM STATE MACHINE CONTROLS triggered by client ui
"""


@app.get("/cmd/capture")
@app.get("/chose/1pic")
def api_chose_1pic_get():
    try:
        model.invokeProcess("arm")
        return "OK"
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=500, detail=f"something went wrong, Exception: {e}")


@ee.on("triggerprocess/chose_1pic")
def evt_chose_1pic_get():
    try:
        model.invokeProcess("arm")
    except Exception as e:
        logger.exception(e)


@app.get("/stats/focuser")
def api_stats_focuser():
    pass
    # return (focusState._lastRunResult)


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


@app.get("/gallery/delete", status_code=status.HTTP_204_NO_CONTENT)
def api_gallery_delete(id: str):
    logger.info(f"gallery_delete requested, id={id}")
    try:
        imageDb.deleteImageById(id)
    except Exception as e:
        logger.exception(e)
        # print(e)
        raise HTTPException(500, f"deleting failed: {e}")


@app.get('/stream.mjpg')
def video_stream():
    return StreamingResponse(imageServer.gen_stream(),
                             media_type='multipart/x-mixed-replace; boundary=frame')


# serve data directory holding images, thumbnails, ...
app.mount('/data', StaticFiles(directory='data'), name="data")


@app.get("/")
async def read_index():
    return FileResponse('web/index.html')

# if not match anything above, default to deliver static files from web directory
app.mount("/", StaticFiles(directory="web"), name="web")


if __name__ == '__main__':
    infoled = InfoLed(ee)

    # load imageserver dynamically because service can be configured https://stackoverflow.com/a/14053838
    imageserverModule = import_module(
        f"lib.{settings.common.IMAGESERVER_BACKEND}")
    cls = getattr(imageserverModule, settings.common.IMAGESERVER_BACKEND)
    imageServer = cls(ee)

    locationService = LocationService(ee)
    exif = Exif(imageServer, locationService)
    imageDb = ImageDb(ee, imageServer, exif)

    if (True):
        ks = KeyboardService(ee)

    # model, machine and fire.
    model = TakePictureMachineModel(ee)
    machine = Machine(model, states=states,
                      transitions=transitions, after_state_change='sse_emit_statechange', initial='idle')
    model.start()

    imageServer.start()

    # first time try to get location
    locationService.start()

    # log all registered listener
    logger.debug(ee.listeners_all())

    # serve files forever
    try:
        # log_level="trace", default info
        config = uvicorn.Config(app=app, host="0.0.0.0",
                                port=8000, log_level="info")
        server = uvicorn.Server(config)
        server.force_exit = True
        # workaround until https://github.com/encode/uvicorn/issues/1579 is fixed and shutdown can be handled properly.
        # Otherwise the stream.mjpg if open will block shutdown of the server
        server.run()
    finally:

        imageServer.stop()
