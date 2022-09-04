import cv2
from queue import Queue
from lib.FocuserImxArdu64 import Focuser
import threading
import time


class FocusState(object):
    def __init__(self):
        self.focus_step = 40
        self.MOVE_TIME = 0.066
        self._lastRunResult = []
        self.sharpnessList = Queue()
        self.lock = threading.Lock()
        self.verbose = False
        self.roi = (0.2, 0.2, 0.6, 0.6)  # x, y, width, height
        self.direction = 1
        self.reset()

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
        self.finish = False


def getROIFrame(roi, frame):
    h, w = frame.shape[:2]
    x_start = int(w * roi[0])
    x_end = x_start + int(w * roi[2])

    y_start = int(h * roi[1])
    y_end = y_start + int(h * roi[3])

    roi_frame = frame[y_start:y_end, x_start:x_end]
    return roi_frame


def statsThread(frameServer, focuser, focusState):
    maxPosition = focuser.opts[focuser.OPT_FOCUS]["MAX_VALUE"]
    minPosition = focuser.opts[focuser.OPT_FOCUS]["MIN_VALUE"]
    lastPosition = focuser.get(focuser.OPT_FOCUS)
    focuser.set(Focuser.OPT_FOCUS, lastPosition)  # init position
    lastTime = time.time()

    sharpnessList = []

    while not focusState.isFinish():

        frame = frameServer.wait_for_lores_frame()

        if frame is None:
            print("error, got no frame, but why?!")
            continue

        roi_frame = getROIFrame(focusState.roi, frame)

        if focusState.verbose:
            cv2.imshow("roi", roi_frame)

        is_success, buffer = cv2.imencode(
            ".jpg", roi_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        #io_buf = io.BytesIO(buffer)

        if time.time() - lastTime >= focusState.MOVE_TIME and not focusState.isFinish():
            if lastPosition != maxPosition:
                focuser.set(Focuser.OPT_FOCUS, lastPosition +
                            (focusState.direction*focusState.focus_step))
                lastTime = time.time()

            # frame is a jpeg; len is the size of the jpeg. the more contrast, the sharper the picture is and thus the bigger the size.
            sharpness = len(buffer)
            item = (lastPosition, sharpness)
            sharpnessList.append(item)
            focusState.sharpnessList.put(item)

            lastPosition += (focusState.direction*focusState.focus_step)

            if lastPosition > maxPosition:
                break

            if lastPosition < minPosition:
                break

    # End of stats.
    focusState.sharpnessList.put((-1, -1))
    focusState._lastRunResult = sharpnessList

    # reverse search direction next time.
    focusState.direction *= -1

    if focusState.verbose:
        print(sharpnessList)
        print("autofocus run finished")


def focusThread(focuser, focusState):
    sharpnessList = []

    continuousDecline = 0
    maxPosition = 0
    lastSharpness = 0
    while not focusState.isFinish():
        position, sharpness = focusState.sharpnessList.get()
        if focusState.verbose:
            print("got stats data: {}, {}".format(position, sharpness))

        if lastSharpness / sharpness >= 1:
            continuousDecline += 1
        else:
            continuousDecline = 0
            maxPosition = position

        lastSharpness = sharpness

        if continuousDecline >= 3:
            focusState.setFinish()

        if position == -1 and sharpness == -1:
            break

        sharpnessList.append((position, sharpness))

    # Mark to finish.
    focusState.setFinish()

    maxItem = max(sharpnessList, key=lambda item: item[1])

    if focusState.verbose:
        print("max: {}".format(maxItem))

    if continuousDecline < 3:
        focuser.set(Focuser.OPT_FOCUS, maxItem[0])
    else:
        focuser.set(Focuser.OPT_FOCUS, maxPosition)


def doFocus(frameServer, focuser, focusState):
    focusState.reset()
    threadAutofocusStats = threading.Thread(target=statsThread, args=(
        frameServer, focuser, focusState), daemon=True)
    threadAutofocusStats.start()

    threadAutofocusFocusSupervisor = threading.Thread(target=focusThread, args=(
        focuser, focusState), daemon=True)
    threadAutofocusFocusSupervisor.start()
