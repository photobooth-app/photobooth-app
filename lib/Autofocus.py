import cv2
from queue import Queue
import threading
import time


class FocusState(object):
    def __init__(self, frameServer, focuser, notifier, CONFIG):
        self._CONFIG = CONFIG

        self._frameServer = frameServer
        self._focuser = focuser
        self._notifier = notifier
        self._notifier.subscribe("onRefocus", self.doFocus)
        self._notifier.subscribe(
            "onCountdownTakePicture", self.setIgnoreFocusRequests)
        self._notifier.subscribe(
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
        if self.isFinish() and self._standby == False:
            self.reset()
            self.setFinish(False)

            threadAutofocusStats = threading.Thread(name='AutofocusStats', target=statsThread, args=(
                self._frameServer, self._focuser, self), daemon=True)
            threadAutofocusStats.start()

            threadAutofocusFocusSupervisor = threading.Thread(name='AutofocusSupervisor', target=focusThread, args=(
                self._focuser, self), daemon=True)
            threadAutofocusFocusSupervisor.start()

        else:
            if self._CONFIG.DEBUG:
                print("Focus is not done yet or in standby.")

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
    lastTime = time.time()

    sharpnessList = []

    while not focusState.isFinish():

        frame = frameServer.wait_for_lores_frame()

        if frame is None:
            print("error, got no frame, but why?!")
            continue

        roi_frame = getROIFrame(focusState._CONFIG.FOCUSER_ROI, frame)

        # if foscusState._CONFIG.DEBUG:
        #    cv2.imshow("roi", roi_frame)

        is_success, buffer = cv2.imencode(
            ".jpg", roi_frame, [cv2.IMWRITE_JPEG_QUALITY, focusState._CONFIG.FOCUSER_JPEG_QUALITY])
        #io_buf = io.BytesIO(buffer)

        if time.time() - lastTime >= focusState._CONFIG.FOCUSER_MOVE_TIME and not focusState.isFinish():
            if lastPosition != maxPosition:
                focuser.set(lastPosition +
                            (focusState.direction*focusState._CONFIG.FOCUSER_STEP))
                lastTime = time.time()

            # frame is a jpeg; len is the size of the jpeg. the more contrast, the sharper the picture is and thus the bigger the size.
            sharpness = len(buffer)
            item = (lastPosition, sharpness)
            sharpnessList.append(item)
            focusState.sharpnessList.put(item)

            lastPosition += (focusState.direction *
                             focusState._CONFIG.FOCUSER_STEP)

            if lastPosition > maxPosition:
                break

            if lastPosition < minPosition:
                break

    # End of stats.
    focusState.sharpnessList.put((-1, -1))
    focusState._lastRunResult = sharpnessList

    # reverse search direction next time.
    focusState.direction *= -1

    if focusState._CONFIG.DEBUG:
        print(sharpnessList)
        print("autofocus run finished")


def focusThread(focuser, focusState):
    sharpnessList = []

    continuousDecline = 0
    maxPosition = 0
    lastSharpness = 0
    while not focusState.isFinish():

        position, sharpness = focusState.sharpnessList.get()
        if focusState._CONFIG.DEBUG:
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

    if focusState._CONFIG.DEBUG:
        print("max: {}".format(maxItem))

    if continuousDecline < 3:
        focuser.set(maxItem[0])
    else:
        focuser.set(maxPosition)
