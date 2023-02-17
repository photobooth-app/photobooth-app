import platform
if platform.system() == "Windows":
    raise OSError("backend v4l2py not supported on windows platform")
from v4l2py import Device


def availableCameraIndexes():
    # checks the first 10 indexes.

    index = 0
    arr = []
    i = 10
    while i > 0:
        if isValidIndex(index):
            arr.append(index)
        index += 1
        i -= 1

    return arr


def isValidIndex(index):
    try:
        cap = Device.from_id(index)
        cap.video_capture.set_format(640, 480, 'MJPG')
        for _ in (cap):
            # got frame, close cam and return true; otherwise false.
            break
        cap.close()
    except Exception as e:
        return False
    else:
        return True


if __name__ == '__main__':
    print(f"probing available webcams")
    print(f"available webcam devices indexes:")
    print(availableCameraIndexes())
