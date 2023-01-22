import cv2


def availableCameraIndexes():
    # checks the first 10 indexes.
    print(f"probing available webcams")
    index = 0
    arr = []
    i = 10
    while i > 0:
        cap = cv2.VideoCapture(index)
        if cap.read()[0]:
            arr.append(index)
            cap.release()
        index += 1
        i -= 1

    print(f"available webcam devices indexes: {arr}")
    return arr


print(availableCameraIndexes())
