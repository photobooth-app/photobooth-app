import io
import logging

import cv2
import pytest
import simplejpeg
from PIL import Image
from turbojpeg import TurboJPEG

from photobooth.services.config import appconfig


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


## encode frame to jpeg comparison


def turbojpeg_encode(frame_from_camera):
    # encoding BGR array to output.jpg with default settings.
    # 85=default quality
    bytes = turbojpeg.encode(frame_from_camera, quality=85)

    return bytes


def pillow_encode(frame_from_camera):
    image = Image.fromarray(frame_from_camera.astype("uint8"), "RGB")
    byte_io = io.BytesIO()
    image.save(byte_io, format="JPEG", quality=85)
    bytes_full = byte_io.getbuffer()

    return bytes_full


def cv2_encode(frame_from_camera):
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
    result, encimg = cv2.imencode(".jpg", frame_from_camera, encode_param)

    return encimg


def simplejpeg_encode(frame_from_camera):
    # encoding BGR array to output.jpg with default settings.
    # 85=default quality
    # simplejpeg uses turbojpeg as lib, but pyturbojpeg also has scaling
    bytes = simplejpeg.encode_jpeg(frame_from_camera, quality=85, fastdct=True)

    return bytes


@pytest.fixture(params=["turbojpeg_encode", "pillow_encode", "cv2_encode", "simplejpeg_encode"])
def library(request):
    # yield fixture instead return to allow for cleanup:
    yield request.param

    # cleanup
    # os.remove(request.param)


def image(file):
    with open(file, "rb") as file:
        in_file_read = file.read()
        frame_from_camera = turbojpeg.decode(in_file_read)

    # yield fixture instead return to allow for cleanup:
    return frame_from_camera


@pytest.fixture()
def image_lores():
    yield image("tests/assets/input_lores.jpg")


@pytest.fixture()
def image_hires():
    yield image("tests/assets/input.jpg")


# needs pip install pytest-benchmark
@pytest.mark.benchmark(
    group="encode_lores",
)
def test_libraries_encode_lores(library, image_lores, benchmark):
    benchmark(eval(library), frame_from_camera=image_lores)
    assert True


# needs pip install pytest-benchmark
@pytest.mark.benchmark(
    group="encode_hires",
)
def test_libraries_encode_hires(library, image_hires, benchmark):
    benchmark(eval(library), frame_from_camera=image_hires)
    assert True
