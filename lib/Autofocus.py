import time
import threading
from lib.FocuserImx519 import Focuser519 as Focuser
from queue import Queue


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


def statsThread(frameServer, focuser, focusState):
    maxPosition = focuser.opts[focuser.OPT_FOCUS]["MAX_VALUE"]
    lastPosition = focuser.get(focuser.OPT_FOCUS)
    focuser.set(Focuser.OPT_FOCUS, lastPosition)  # init position
    lastTime = time.time()

    sharpnessList = []

    while not focusState.isFinish():

        frame = frameServer.wait_for_lores_frame()

        if frame is None:
            print("error, got no frame, but why?!")
            continue

        if time.time() - lastTime >= focusState.MOVE_TIME and not focusState.isFinish():
            if lastPosition != maxPosition:
                focuser.set(Focuser.OPT_FOCUS, lastPosition +
                            (focusState.direction*focusState.FOCUS_SETP))
                lastTime = time.time()

            # frame is a jpeg; len is the size of the jpeg. the more contrast, the sharper the picture is and thus the bigger the size.
            sharpness = len(frame)
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
