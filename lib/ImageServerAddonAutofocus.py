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
from ImageServerAddonAutofocusFocuser import ImageServerAddonAutofocusFocuser
from RepeatedTimer import RepeatedTimer
logger = logging.getLogger(__name__)


class ImageServerAddonAutofocus(object):
    def __init__(self, imageServer: ImageServerAbstract, ee: EventEmitter):
        self._imageServer: ImageServerAbstract = imageServer
        self._focuser = ImageServerAddonAutofocusFocuser()
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
        self.sharpnessList = Queue()
        self.lock = threading.Lock()
        self.direction = 1

        self.setAllowFocusRequests()
        self.reset()

        self._rt = RepeatedTimer(settings.common.FOCUSER_REPEAT_TRIGGER,
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


def statsThread(imageServer: ImageServerAbstract, imageServerAddonAutofocusFocuser: ImageServerAddonAutofocusFocuser, imageServerAddonAutofocus: ImageServerAddonAutofocus):
    maxPosition = imageServerAddonAutofocusFocuser.MAX_VALUE
    minPosition = imageServerAddonAutofocusFocuser.MIN_VALUE
    lastPosition = imageServerAddonAutofocusFocuser.get()
    # focuser.set(lastPosition)  # init position
    jpeg = TurboJPEG()
    lastTime = time.time()
    skippedFrameCounter = 0
    sharpnessList = []

    while not imageServerAddonAutofocus.isFinish():
        try:
            frame = imageServer._wait_for_autofocus_frame()
        except NotImplementedError:
            logger.error(
                f"imageserver backend not to deliver lores frames for autofocus - please disable autofocus")
            imageServerAddonAutofocus.stopRegularAutofocusTimer()
            imageServerAddonAutofocus.reset()
            break
        except IOError:
            logger.warning(
                f"imageserver did not deliver frames, aborting cycle (should occur only if service stopped!)")
            imageServerAddonAutofocus.stopRegularAutofocusTimer()
            imageServerAddonAutofocus.reset()
            break

        if time.time() - lastTime >= settings.common.FOCUSER_MOVE_TIME and not imageServerAddonAutofocus.isFinish():
            lastTime = time.time()

            nextPosition = lastPosition + \
                (imageServerAddonAutofocus.direction *
                 settings.common.FOCUSER_STEP)

            if nextPosition < maxPosition and nextPosition > minPosition:
                imageServerAddonAutofocusFocuser.set(nextPosition)

            roi_frame = getROIFrame(
                settings.common.FOCUSER_ROI, frame)
            buffer = jpeg.encode(
                roi_frame, quality=settings.common.FOCUSER_JPEG_QUALITY)

            # frame is a jpeg; len is the size of the jpeg. the more contrast, the sharper the picture is and thus the bigger the size.
            sharpness = len(buffer)
            item = (lastPosition, sharpness)
            sharpnessList.append(item)
            imageServerAddonAutofocus.sharpnessList.put(item)

            lastPosition += (imageServerAddonAutofocus.direction *
                             settings.common.FOCUSER_STEP)

            if lastPosition > maxPosition:
                break

            if lastPosition < minPosition:
                break
        else:
            # Focus motor cannot catch up with camera fps. This is not a problem actually.
            skippedFrameCounter += 1

    # End of stats.
    imageServerAddonAutofocus.sharpnessList.put((-1, -1))
    imageServerAddonAutofocus._lastRunResult = sharpnessList

    # reverse search direction next time.
    imageServerAddonAutofocus.direction *= -1

    imageServerAddonAutofocus._ee.emit("publishSSE", sse_event="autofocus/sharpness",
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
