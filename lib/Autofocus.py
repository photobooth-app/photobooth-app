import os
from os.path import exists as file_exists
from turbojpeg import TurboJPEG
import json
from queue import Queue
import threading
import time
import logging
from lib.ConfigSettings import settings
from lib.ImageServerAbstract import ImageServerAbstract
from lib.RepeatedTimer import RepeatedTimer
logger = logging.getLogger(__name__)


class Focuser:
    """
    ###
    # This script works after installing the driver for 16mp imx519 driver from arducam
    # only driver necessary, not the libcamera apps
    # How to install the driver
    # https://www.arducam.com/docs/cameras-for-raspberry-pi/raspberry-pi-libcamera-guide/how-to-use-arducam-16mp-camera-on-rapberry-pi/
    # You can use our auto-install script to install the driver for arducam 64MP camera:
    # wget - O install_pivariety_pkgs.sh https: // github.com/ArduCAM/Arducam-Pivariety-V4L2-Driver/releases/download/install_script/install_pivariety_pkgs.sh
    # chmod + x install_pivariety_pkgs.sh
    # ./install_pivariety_pkgs.sh - p imx519_kernel_driver_low_speed
    #
    # driver may have to be reinstalled after system updates!
    """

    def __init__(self):
        self.focus_value = 0
        self._device = settings.common.FOCUSER_DEVICE
        self.MAX_VALUE = settings.common.FOCUSER_MAX_VALUE
        self.MIN_VALUE = settings.common.FOCUSER_MIN_VALUE

        self.reset()

    def reset(self):
        self.set(settings.common.FOCUSER_DEF_VALUE)

    def get(self):
        return self.focus_value

    def set(self, value):
        if value > settings.common.FOCUSER_MAX_VALUE:
            value = settings.common.FOCUSER_MAX_VALUE
        elif value < settings.common.FOCUSER_MIN_VALUE:
            value = settings.common.FOCUSER_MIN_VALUE

        value = int(value)
        try:
            os.system(
                "v4l2-ctl -c focus_absolute={} -d {}".format(value, self._device))
        except Exception as e:
            logger.exception(e)
            logger.error(f"Error on focus command: {e}")

        self.focus_value = value


class FocusState(object):
    def __init__(self, imageServer, ee):
        self._imageServer: ImageServerAbstract = imageServer
        self._focuser = Focuser()
        self._ee = ee
        self._ee.on("onRefocus", self.doFocus)
        self._ee.on(
            "statemachine/armed", self.setIgnoreFocusRequests)
        self._ee.on(
            "statemachine/finished", self.setAllowFocusRequests)

        self._ee.on("onCaptureMode", self.setIgnoreFocusRequests)
        self._ee.on("onPreviewMode", self.setAllowFocusRequests)

        self._lastRunResult = []
        self.sharpnessList = Queue()
        self.lock = threading.Lock()
        self.direction = 1

        self.setAllowFocusRequests()
        self.reset()

        self._rt = RepeatedTimer(settings.common.FOCUSER_REPEAT_TRIGGER,
                                 self.doFocus)

        self.startRegularAutofocusTimer()

    def startRegularAutofocusTimer(self):
        self._rt.start()

    def stopRegularAutofocusTimer(self):
        self._rt.stop()

    def setIgnoreFocusRequests(self):
        self._standby = True

    def setAllowFocusRequests(self):
        self._standby = False

    def doFocus(self):
        # guard to perfom autofocus only once at a time
        if self.isFinish() and self._standby == False and settings.common.FOCUSER_ENABLED:
            self.reset()
            self.setFinish(False)

            threadAutofocusStats = threading.Thread(name='AutofocusStats', target=statsThread, args=(
                self._imageServer, self._focuser, self), daemon=True)
            threadAutofocusStats.start()

            threadAutofocusFocusSupervisor = threading.Thread(name='AutofocusSupervisor', target=focusThread, args=(
                self._focuser, self), daemon=True)
            threadAutofocusFocusSupervisor.start()

        else:
            logger.debug("Focus is not done yet or in standby.")

    def isFinish(self):
        self.lock.acquire()
        finish = self.finish
        self.lock.release()
        return finish

    def setFinish(self, finish=True):
        self.lock.acquire()
        self.finish = finish
        self.lock.release()

    def reset(self):
        self.sharpnessList = Queue()
        self.finish = True


def getROIFrame(roi, frame):
    h, w = frame.shape[:2]
    x_start = int(w * roi[0])
    x_end = x_start + int(w * roi[2])

    y_start = int(h * roi[1])
    y_end = y_start + int(h * roi[3])

    roi_frame = frame[y_start:y_end, x_start:x_end]
    return roi_frame


def statsThread(imageServer: ImageServerAbstract, focuser: Focuser, focusState: FocusState):
    maxPosition = focuser.MAX_VALUE
    minPosition = focuser.MIN_VALUE
    lastPosition = focuser.get()
    # focuser.set(lastPosition)  # init position
    jpeg = TurboJPEG()
    lastTime = time.time()
    skippedFrameCounter = 0
    sharpnessList = []

    while not focusState.isFinish():
        try:
            frame = imageServer.wait_for_lores_frame()
        except NotImplementedError as e:
            logger.error(
                f"imageserver backend not to deliver lores frames for autofocus - please disable autofocus")
            focusState.stopRegularAutofocusTimer()
            focusState.reset()
            break

        if time.time() - lastTime >= settings.common.FOCUSER_MOVE_TIME and not focusState.isFinish():
            lastTime = time.time()

            nextPosition = lastPosition + \
                (focusState.direction *
                 settings.common.FOCUSER_STEP)

            if nextPosition < maxPosition and nextPosition > minPosition:
                focuser.set(nextPosition)

            roi_frame = getROIFrame(
                settings.common.FOCUSER_ROI, frame)
            buffer = jpeg.encode(
                roi_frame, quality=settings.common.FOCUSER_JPEG_QUALITY)

            # frame is a jpeg; len is the size of the jpeg. the more contrast, the sharper the picture is and thus the bigger the size.
            sharpness = len(buffer)
            item = (lastPosition, sharpness)
            sharpnessList.append(item)
            focusState.sharpnessList.put(item)

            lastPosition += (focusState.direction *
                             settings.common.FOCUSER_STEP)

            if lastPosition > maxPosition:
                break

            if lastPosition < minPosition:
                break
        else:
            # Focus motor cannot catch up with camera fps. This is not a problem actually.
            skippedFrameCounter += 1

    # End of stats.
    focusState.sharpnessList.put((-1, -1))
    focusState._lastRunResult = sharpnessList

    # reverse search direction next time.
    focusState.direction *= -1

    focusState._ee.emit("publishSSE", sse_event="autofocus/sharpness",
                        sse_data=json.dumps(sharpnessList))

    logger.debug(f"autofocus run finished, sharpnessList={sharpnessList}")
    if (skippedFrameCounter):
        logger.debug(
            f"skipped {skippedFrameCounter} frames because motor cannot catch up with FPS of camera. not a problem, could be tuned.")


def focusThread(focuser, focusState):
    sharpnessList = []
    CONTINUOUSDECLINE_REQ = 6
    continuousDecline = 0
    maxPosition = 0
    lastSharpness = 0
    while not focusState.isFinish():

        position, sharpness = focusState.sharpnessList.get()

        if lastSharpness / sharpness >= 1:
            continuousDecline += 1
        else:
            continuousDecline = 0
            maxPosition = position

        lastSharpness = sharpness

        if continuousDecline >= CONTINUOUSDECLINE_REQ:
            focusState.setFinish()

        if position == -1 and sharpness == -1:
            break

        sharpnessList.append((position, sharpness))

    # Mark to finish.
    focusState.setFinish()

    maxItem = max(sharpnessList, key=lambda item: item[1])

    logger.debug(f"max: {maxItem}")

    if continuousDecline < CONTINUOUSDECLINE_REQ:
        focuser.set(maxItem[0])
    else:
        focuser.set(maxPosition)
