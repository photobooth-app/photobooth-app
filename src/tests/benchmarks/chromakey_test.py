import logging

import cv2
import numpy as np
import pytest
from PIL import Image

logger = logging.getLogger(name=None)


GREEN_RANGE_MIN_HSV = (45, 50, 50)
GREEN_RANGE_MAX_HSV = (65, 255, 255)


def opencv_chromakey(pil_image: Image.Image):
    BLUR_SIZE = 2
    DILATE_SIZE = 4

    def convert_from_cv2_to_image(img: np.ndarray) -> Image.Image:
        return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA))

    def convert_from_image_to_cv2(img: Image.Image) -> np.ndarray:
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    # choose hsv parameters: https://docs.opencv.org/4.x/df/d9d/tutorial_py_colorspaces.html
    # https://stackoverflow.com/questions/10948589/choosing-the-correct-upper-and-lower-hsv-boundaries-for-color-detection-withcv/48367205#48367205
    # https://stackoverflow.com/questions/48109650/how-to-detect-two-different-colors-using-cv2-inrange-in-python-opencv
    # https://www.geeksforgeeks.org/opencv-invert-mask/
    # https://stackoverflow.com/questions/51719472/remove-green-background-screen-from-image-using-opencv-python
    # https://docs.opencv.org/3.4/d9/d61/tutorial_py_morphological_ops.html

    frame = convert_from_image_to_cv2(pil_image)
    ## convert to hsv
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # mask of green
    mask = cv2.inRange(hsv, np.array(GREEN_RANGE_MIN_HSV), np.array(GREEN_RANGE_MAX_HSV))
    # cv2.imshow("Input", mask)
    # cv2.waitKey(0)
    # remove noise/false positives within people area
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((DILATE_SIZE, DILATE_SIZE), np.uint8))
    # dilate mask a bit to remove bit more when blurred
    mask = cv2.dilate(mask, np.ones((DILATE_SIZE, DILATE_SIZE), np.uint8), iterations=1)
    # cv2.imshow("Input", mask)
    # cv2.waitKey(0)

    # Inverting the mask
    mask_inverted = cv2.bitwise_not(mask)

    # enhance edges by blur# blur threshold image
    blur = cv2.GaussianBlur(mask_inverted, (0, 0), sigmaX=BLUR_SIZE, sigmaY=BLUR_SIZE, borderType=cv2.BORDER_DEFAULT)

    # actually remove the background (so if transparency is ignored later in processing,
    # the removed parts are black instead just return)
    result = cv2.bitwise_and(frame, frame, mask=blur)
    # create result with transparent channel
    result = cv2.cvtColor(result, cv2.COLOR_BGR2BGRA)
    result[:, :, 3] = blur  # add mask to image as alpha channel

    # cv2.imshow("Input", result)
    # cv2.waitKey(0)
    return convert_from_cv2_to_image(result)


def opencv_chromakey_live(pil_image: Image.Image):
    # reduced quality optimized for higher speed.

    def convert_from_cv2_to_image(img: np.ndarray) -> Image.Image:
        return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA))

    def convert_from_image_to_cv2(img: Image.Image) -> np.ndarray:
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    # choose hsv parameters: https://docs.opencv.org/4.x/df/d9d/tutorial_py_colorspaces.html
    # https://stackoverflow.com/questions/10948589/choosing-the-correct-upper-and-lower-hsv-boundaries-for-color-detection-withcv/48367205#48367205
    # https://stackoverflow.com/questions/48109650/how-to-detect-two-different-colors-using-cv2-inrange-in-python-opencv
    # https://www.geeksforgeeks.org/opencv-invert-mask/
    # https://stackoverflow.com/questions/51719472/remove-green-background-screen-from-image-using-opencv-python
    # https://docs.opencv.org/3.4/d9/d61/tutorial_py_morphological_ops.html

    frame = convert_from_image_to_cv2(pil_image)
    ## convert to hsv
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # mask of green
    mask = cv2.inRange(hsv, np.array(GREEN_RANGE_MIN_HSV), np.array(GREEN_RANGE_MAX_HSV))

    # Inverting the mask
    mask_inverted = cv2.bitwise_not(mask)

    # actually remove the background (so if transparency is ignored later in processing,
    # the removed parts are black instead just return)
    result = cv2.bitwise_and(frame, frame, mask=mask_inverted)
    # create result with transparent channel
    result = cv2.cvtColor(result, cv2.COLOR_BGR2BGRA)
    result[:, :, 3] = mask_inverted  # add mask to image as alpha channel

    # cv2.imshow("Input", result)
    # cv2.waitKey(0)
    return convert_from_cv2_to_image(result)


@pytest.fixture(params=["opencv_chromakey", "opencv_chromakey_live"])
def library(request):
    # yield fixture instead return to allow for cleanup:
    yield request.param

    # cleanup
    # os.remove(request.param)


@pytest.fixture()
def image():
    yield Image.open("src/tests/assets/greenscreen.jpg")


# needs pip install pytest-benchmark
@pytest.mark.benchmark(
    group="chromakey",
)
def test_libraries_chromakey(library, image, benchmark):
    pil_image_chromakeyed = benchmark(eval(library), pil_image=image)
    # pil_image_chromakeyed = opencv_chromakey(pil_image=image_lores)
    pil_image_chromakeyed.convert("RGB")

    assert True
