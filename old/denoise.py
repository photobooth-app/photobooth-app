#!/usr/bin/python3


import cv2 as cv
import cv2

from picamera2 import Picamera2

cv2.startWindowThread()

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(
    main={"format": 'XRGB8888', "size": (640, 480)}))
picam2.start()

while True:
    im = picam2.capture_array()
    dst = cv.fastNlMeansDenoisingColored(im, None, 3, 3, 5, 15)

    cv2.imshow("original", im)
    cv2.imshow("denoise", dst)
