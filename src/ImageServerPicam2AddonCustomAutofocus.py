from smbus import SMBus
from pymitter import EventEmitter
import os
from os.path import exists as file_exists
from turbojpeg import TurboJPEG
import json
from queue import Queue
import threading
import time
import logging
from ConfigSettings import settings
from ImageServerAbstract import ImageServerAbstract
from RepeatedTimer import RepeatedTimer
logger = logging.getLogger(__name__)


class ImageServerPicam2AddonCustomAutofocus(object):
    def __init__(self, imageServer: ImageServerAbstract, ee: EventEmitter):
        self._imageServer: ImageServerAbstract = imageServer
        self._ee = ee
        self._ee.on("onRefocus",
                    self.doFocus)
        self._ee.on("statemachine/armed",
                    self.setIgnoreFocusRequests)
        self._ee.on("statemachine/finished",
                    self.setAllowFocusRequests)
        self._ee.on("onCaptureMode",
                    self.setIgnoreFocusRequests)
        self._ee.on("onPreviewMode",
                    self.setAllowFocusRequests)

        self._lastRunResult = []
        self._lastFinalPosition = settings.focuser.DEF_VALUE
        self.sharpnessList = Queue()
        self.lock = threading.Lock()
        self.direction = 1

        self.setAllowFocusRequests()
        self.reset()

        self._rt = RepeatedTimer(settings.focuser.REPEAT_TRIGGER,
                                 self.triggerRegularTimedFocus)

        self.startRegularAutofocusTimer()

    def startRegularAutofocusTimer(self):
        self._rt.start()

    def stopRegularAutofocusTimer(self):
        self._rt.stop()

    def abortOngoingFocusThread(self):
        logger.debug("abort ongoing focus thread")
        self.setFinish(True)

    def setIgnoreFocusRequests(self):
        self._standby = True

    def setAllowFocusRequests(self):
        self._standby = False

    def triggerRegularTimedFocus(self):
        if not self._standby:
            self.doFocus()

    def doFocus(self):
        # guard to perfom autofocus only once at a time
        if self.isFinish() and self._standby == False and settings.focuser.ENABLED:
            self.reset()
            self.setFinish(False)

            threadAutofocusStats = threading.Thread(name='AutofocusStats', target=statsThread, args=(
                self._imageServer, self), daemon=True)
            threadAutofocusStats.start()

            threadAutofocusFocusSupervisor = threading.Thread(name='AutofocusSupervisor', target=focusThread, args=(
                self,), daemon=True)
            threadAutofocusFocusSupervisor.start()

        else:
            logger.warn("Focus is not done yet or in standby.")

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
        self.setFinish(True)


def getROIFrame(roi, frame):
    h, w = frame.shape[:2]
    x_start = int(w * roi[0])
    x_end = x_start + int(w * roi[2])

    y_start = int(h * roi[1])
    y_end = y_start + int(h * roi[3])

    roi_frame = frame[y_start:y_end, x_start:x_end]
    return roi_frame


def statsThread(imageServer: ImageServerAbstract, imageServerAddonCustomAutofocus: ImageServerPicam2AddonCustomAutofocus):
    maxPosition = settings.focuser.MAX_VALUE
    minPosition = settings.focuser.MIN_VALUE
    lastPosition = imageServerAddonCustomAutofocus._lastFinalPosition

    jpeg = TurboJPEG()
    lastTime = time.time()
    skippedFrameCounter = 0
    sharpnessList = []

    while not imageServerAddonCustomAutofocus.isFinish():
        try:
            frame = imageServer._wait_for_lores_frame()
        except NotImplementedError:
            logger.error(
                f"imageserver backend not to deliver lores frames for autofocus - please disable autofocus")
            imageServerAddonCustomAutofocus.stopRegularAutofocusTimer()
            imageServerAddonCustomAutofocus.reset()
            break
        except IOError:
            logger.warning(
                f"imageserver did not deliver frames, aborting cycle (should occur only if service stopped!)")
            imageServerAddonCustomAutofocus.stopRegularAutofocusTimer()
            imageServerAddonCustomAutofocus.reset()
            break

        if time.time() - lastTime >= settings.focuser.MOVE_TIME and not imageServerAddonCustomAutofocus.isFinish():
            lastTime = time.time()

            nextPosition = lastPosition + \
                (imageServerAddonCustomAutofocus.direction *
                 settings.focuser.STEP)

            if nextPosition < maxPosition and nextPosition > minPosition:
                set_focus_position(nextPosition)

            # calc window x, y, width, height
            roi = (settings.focuser.ROI/100,
                   (settings.focuser.ROI/100),
                   (1-(2*settings.focuser.ROI/100),
                    1-(2*settings.focuser.ROI/100)))
            roi_frame = getROIFrame(roi, frame)
            buffer = jpeg.encode(
                roi_frame, quality=80)

            # frame is a jpeg; len is the size of the jpeg. the more contrast, the sharper the picture is and thus the bigger the size.
            sharpness = len(buffer)
            item = (lastPosition, sharpness)
            sharpnessList.append(item)
            imageServerAddonCustomAutofocus.sharpnessList.put(item)

            lastPosition += (imageServerAddonCustomAutofocus.direction *
                             settings.focuser.STEP)

            if lastPosition > maxPosition:
                break

            if lastPosition < minPosition:
                break
        else:
            # Focus motor cannot catch up with camera fps. This is not a problem actually.
            skippedFrameCounter += 1

    # End of stats.
    imageServerAddonCustomAutofocus.sharpnessList.put((-1, -1))
    imageServerAddonCustomAutofocus._lastRunResult = sharpnessList

    # reverse search direction next time.
    imageServerAddonCustomAutofocus.direction *= -1

    imageServerAddonCustomAutofocus._ee.emit("publishSSE", sse_event="autofocus/sharpness",
                                             sse_data=json.dumps(sharpnessList))

    logger.debug(f"autofocus run finished, sharpnessList={sharpnessList}")
    if (skippedFrameCounter):
        logger.debug(
            f"skipped {skippedFrameCounter} frames because motor cannot catch up with FPS of camera. not a problem, could be tuned.")


def focusThread(imageServerAddonCustomAutofocus: ImageServerPicam2AddonCustomAutofocus):
    sharpnessList = []
    CONTINUOUSDECLINE_REQ = 6
    continuousDecline = 0
    maxPosition = 0
    lastSharpness = 0
    while not imageServerAddonCustomAutofocus.isFinish():

        position, sharpness = imageServerAddonCustomAutofocus.sharpnessList.get()

        if lastSharpness / sharpness >= 1:
            continuousDecline += 1
        else:
            continuousDecline = 0
            maxPosition = position

        lastSharpness = sharpness

        if continuousDecline >= CONTINUOUSDECLINE_REQ:
            imageServerAddonCustomAutofocus.setFinish()

        if position == -1 and sharpness == -1:
            break

        sharpnessList.append((position, sharpness))

    # Mark to finish.
    imageServerAddonCustomAutofocus.setFinish()

    maxItem = max(sharpnessList, key=lambda item: item[1])

    logger.debug(f"max: {maxItem}")

    if continuousDecline < CONTINUOUSDECLINE_REQ:
        set_focus_position(maxItem[0])
        imageServerAddonCustomAutofocus._lastFinalPosition = maxItem[0]
    else:
        set_focus_position(maxPosition)
        imageServerAddonCustomAutofocus._lastFinalPosition = maxPosition


def set_focus_position(position):
    value = int(position)
    try:
        focuser = settings.focuser.focuser_backend.value
        if focuser == "arducam_imx477":
            arducam_imx477_focuser(value)
        elif focuser == "arducam_imx519":
            arducam_imx519_64mp_focuser(value)
        elif focuser == "arducam_64mp":
            arducam_imx519_64mp_focuser(value)
        else:
            raise Exception("invalid focuser model selected")

    except Exception as e:
        logger.exception(e)
        logger.error(f"Error on focus command: {e}")


def arducam_imx477_focuser(position):
    bus = 10
    i2caddress = 0x0c

    value = (position << 4) & 0x3ff0
    dat1 = (value >> 8) & 0x3f
    dat2 = value & 0xf0

    i2cbus = SMBus(bus)
    i2cbus.write_byte_data(i2caddress, dat1, dat2)

    # i2c bus above same as in arducam libs:
    # os.system("i2cset -y %d 0x0c %d %d" % (bus, dat1, dat2))


def arducam_imx519_64mp_focuser(position):
    os.system(
        "v4l2-ctl -c focus_absolute={} -d /dev/v4l-subdev1".format(position))
