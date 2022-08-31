import time
import cv2
import numpy as np
import threading
from .Focuser519 import Focuser519 as Focuser

try:
    from Queue import Queue
except ModuleNotFoundError:
    from queue import Queue


def laplacian(img):
    img_gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    img_sobel = np.abs(cv2.Laplacian(img_gray, cv2.CV_16S, ksize=3))
    return cv2.mean(img_sobel)[0]


class FocusState(object):
    def __init__(self):
        self.FOCUS_SETP = 70
        self.MOVE_TIME = 0.066

        self.lock = threading.Lock()
        self.verbose = False
        self.roi = (0.1, 0.1, 0.8, 0.8)  # x, y, width, height
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


def statsThread(camera, focuser, focusState):
    maxPosition = focuser.opts[focuser.OPT_FOCUS]["MAX_VALUE"]
    lastPosition = focuser.get(focuser.OPT_FOCUS)
    focuser.set(Focuser.OPT_FOCUS, lastPosition)  # init position
    time.sleep(0.01)
    lastTime = time.time()

    sharpnessList = []

    while not focusState.isFinish():
        frame = camera.capture_array()

        if frame is None:
            continue

        roi_frame = getROIFrame(focusState.roi, frame)

        if focusState.verbose:
            cv2.imshow("ROI", roi_frame)

        if time.time() - lastTime >= focusState.MOVE_TIME and not focusState.isFinish():
            if lastPosition != maxPosition:
                focuser.set(Focuser.OPT_FOCUS, lastPosition +
                            (focusState.direction*focusState.FOCUS_SETP))
                lastTime = time.time()

            sharpness = laplacian(roi_frame)
            # print("position: {}, sharpness: {}".format(lastPosition, sharpness))
            item = (lastPosition, sharpness)
            sharpnessList.append(item)
            focusState.sharpnessList.put(item)

            lastPosition += (focusState.direction*focusState.FOCUS_SETP)

            if lastPosition > maxPosition:
                break

    # End of stats.
    focusState.sharpnessList.put((-1, -1))

    # reverse search direction next time.
    focusState.direction *= -1

    # nasa type of math...
    # parabel = np.polyfit([x[0] for x in list(focusState.sharpnessList)], [
    #                     y[1] for y in list(focusState.sharpnessList)], 2)

    if focusState.verbose:
        for sharpness in sharpnessList:
            print(sharpness)

        print("stats done.")


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


def doFocus(camera, focuser, focusState):
    focusState.reset()  # fix: reset because otherwise focusthread will not loop
    statsThread_ = threading.Thread(
        target=statsThread, args=(camera, focuser, focusState))
    statsThread_.daemon = True
    statsThread_.start()

    focusThread_ = threading.Thread(
        target=focusThread, args=(focuser, focusState))
    focusThread_.daemon = True
    focusThread_.start()
