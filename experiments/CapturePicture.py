import signal
import time
import argparse
from old.RpiCamera import Camera
from lib.FocuserImx519 import Focuser519 as Focuser
from lib.Autofocus import FocusState, doFocus
exit_ = False


def sigint_handler(signum, frame):
    global exit_
    exit_ = True


signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGTERM, sigint_handler)


def parse_cmdline():
    parser = argparse.ArgumentParser(
        description='Photobooth Autofocus Libcamera PiCam2 Capture Picture')

    parser.add_argument('-d', '--dev', type=str, nargs=None, required=False, default="/dev/v4l-subdev1",
                        help='Set device for v4l2-ctl, default: /dev/v4l-subdev1')

    parser.add_argument('-o', '--output', type=str, nargs=None, required=False, default="./image.jpg",
                        help='Store file to given file')

    parser.add_argument('-v', '--verbose',
                        action="store_true", help='Print debug info.')

    return parser.parse_args()


if __name__ == "__main__":

    signal.raise_signal(signal.SIGINT)

    args = parse_cmdline()
    camera = Camera()
    camera.start_preview(False)

    time.sleep(0.2)

    focuser = Focuser(args.dev)
    focuser.verbose = args.verbose

    focusState = FocusState()
    focusState.verbose = args.verbose
    doFocus(camera, focuser, focusState)

    # camera.cam.start(show_preview=True)

    while not focusState.isFinish():
        time.sleep(0.2)

    print("focus finished, capture now")
    # print(camera.cam.camera_controls)
    #camera.cam.set_controls({"ExposureTime": 10000})

    capture_config = camera.cam.create_still_configuration()
    camera.cam.switch_mode_and_capture_file(capture_config, args.output)
    camera.close()

    print("Done")
