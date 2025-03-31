import logging
import os

os.environ["OPENCV_LOG_LEVEL"] = "DEBUG"

import cv2
import numpy as np
import pytest
from PIL import Image

logger = logging.getLogger(name=None)


def pil_to_mp4_ffmpeg(images: list[Image.Image]):
    pass
    # not available


def pil_to_gif_ffmpeg(images: list[Image.Image]):
    pass


def pil_to_mp4_pyav(images: list[Image.Image]):
    pass


def pil_to_gif_cv2(images: list[Image.Image]):
    pass
    # not available.


def pil_to_mp4_cv2(images: list[Image.Image], _tmp_path):
    (width, height) = images[0].size[:2]

    # needs https://github.com/opencv/opencv/tree/master/3rdparty/ffmpeg cisco openh264 installed!
    # warning: no error messages about failed creation!
    # fourcc = cv2.VideoWriter.fourcc(*"H264")
    # video = cv2.VideoWriter(f"{_tmp_path}/test.h264.mp4", fourcc, 1, (width, height))
    # for image in images:
    #     video.write(cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR))
    # video.release()

    fourcc = cv2.VideoWriter.fourcc(*"mp4v")
    video = cv2.VideoWriter(f"{_tmp_path}/test.mp4v.mp4", fourcc, 1, (width, height))
    for image in images:
        video.write(cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR))
    video.release()

    # fourcc = cv2.VideoWriter.fourcc(*"XVID")
    # video = cv2.VideoWriter(f"{_tmp_path}/test.xvid.mp4", fourcc, 1, (width, height))
    # for image in images:
    #     video.write(cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR))
    # video.release()

    # fourcc = cv2.VideoWriter.fourcc(*"MJPG")
    # video = cv2.VideoWriter(f"{_tmp_path}/test.mjpg", fourcc, 1, (width, height))
    # for image in images:
    #     video.write(cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR))
    # video.release()

    # fourcc = cv2.VideoWriter.fourcc(*"MJPG")
    # print(fourcc)
    # video = cv2.VideoWriter(f"{_tmp_path}/test.avi", fourcc, 1, (width, height))
    # for image in images:
    #     video.write(cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR))
    # video.release()


def images() -> list[Image.Image]:
    img = Image.new("RGB", (1500, 1000), color="darkred")
    imgs = [img]

    # draw stuff that goes on every frame here
    for _ in range(10):
        imgs.append(img.copy())

    return imgs


@pytest.mark.benchmark(group="merge_frame")
def test_pil_to_mp4_cv2(benchmark, tmp_path):
    benchmark(pil_to_mp4_cv2, images=images(), _tmp_path=tmp_path)
