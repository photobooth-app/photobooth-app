from turbojpeg import TurboJPEG
import json
from queue import Queue
import threading
import time
import logging

logger = logging.getLogger(__name__)


class FocusState(object):
    def __init__(self, frameServer, focuser, ee, CONFIG):
        self._CONFIG = CONFIG

        self._frameServer = frameServer
        self._focuser = focuser
        self._ee = ee
        self._ee.on("onRefocus", self.doFocus)
        self._ee.on(
            "onCountdownTakePicture", self.setIgnoreFocusRequests)
        self._ee.on(
            "onTakePictureFinished", self.setAllowFocusRequests)

        self._lastRunResult = []
        self.sharpnessList = Queue()
        self.lock = threading.Lock()
        self.direction = 1

        self.setAllowFocusRequests()
        self.reset()

    def setIgnoreFocusRequests(self):
        self._standby = True

    def setAllowFocusRequests(self):
        self._standby = False

    def doFocus(self):
        # guard to perfom autofocus only once at a time
        if self.isFinish() and self._standby == False and self._CONFIG._current_config['FOCUSER_ENABLED']:
            self.reset()
            self.setFinish(False)

            threadAutofocusStats = threading.Thread(name='AutofocusStats', target=statsThread, args=(
                self._frameServer, self._focuser, self), daemon=True)
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


def statsThread(frameServer, focuser, focusState):
    maxPosition = focuser.MAX_VALUE
    minPosition = focuser.MIN_VALUE
    lastPosition = focuser.get()
    # focuser.set(lastPosition)  # init position
    jpeg = TurboJPEG()
    lastTime = time.time()
    skippedFrameCounter = 0
    sharpnessList = []

    while not focusState.isFinish():

        frame = frameServer.wait_for_lores_frame()

        if time.time() - lastTime >= focusState._CONFIG._current_config["FOCUSER_MOVE_TIME"] and not focusState.isFinish():
            lastTime = time.time()

            nextPosition = lastPosition + \
                (focusState.direction *
                 focusState._CONFIG._current_config["FOCUSER_STEP"])

            if nextPosition < maxPosition and nextPosition > minPosition:
                focuser.set(nextPosition)

            roi_frame = getROIFrame(
                focusState._CONFIG._current_config["FOCUSER_ROI"], frame)
            buffer = jpeg.encode(
                roi_frame, quality=focusState._CONFIG._current_config["FOCUSER_JPEG_QUALITY"])

            # frame is a jpeg; len is the size of the jpeg. the more contrast, the sharper the picture is and thus the bigger the size.
            sharpness = len(buffer)
            item = (lastPosition, sharpness)
            sharpnessList.append(item)
            focusState.sharpnessList.put(item)

            lastPosition += (focusState.direction *
                             focusState._CONFIG._current_config["FOCUSER_STEP"])

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
