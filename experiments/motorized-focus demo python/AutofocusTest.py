import time
import signal
import cv2
import argparse
from RpiCamera import Camera
from Focuser519 import Focuser519 as Focuser
from Autofocus import FocusState, doFocus

exit_ = False


def sigint_handler(signum, frame):
    global exit_
    exit_ = True


signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGTERM, sigint_handler)


def parse_cmdline():
    parser = argparse.ArgumentParser(
        description='Arducam IMX519 Autofocus Demo.')

    parser.add_argument('-i', '--i2c-bus', type=int, nargs=None, required=True,
                        help='Set i2c bus, for A02 is 6, for B01 is 7 or 8, for Jetson Xavier NX it is 9 and 10.')

    parser.add_argument('-v', '--verbose',
                        action="store_true", help='Print debug info.')

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_cmdline()
    camera = Camera()
    camera.start_preview(False)
    focuser = Focuser(args.i2c_bus)
    focuser.verbose = args.verbose

    focusState = FocusState()
    focusState.verbose = args.verbose
    doFocus(camera, focuser, focusState)

    start = time.time()
    frame_count = 0

    while not exit_:
        frame = camera.getFrame()
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        cv2.imshow("Test", img)
        key = cv2.waitKey(1)
        if key == ord('q'):
            exit_ = True
        if key == ord('f'):
            if focusState.isFinish():
                focusState.reset()
                doFocus(camera, focuser, focusState)
            else:
                print("Focus is not done yet.")

        frame_count += 1
        if time.time() - start >= 1:
            print("{}fps".format(frame_count))
            start = time.time()
            frame_count = 0
    cv2.imwrite("image{}.jpg".format(0), camera.getFrame())
    camera.close()
