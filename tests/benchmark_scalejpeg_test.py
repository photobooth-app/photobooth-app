import io
import logging

import cv2
import numpy
import pytest
from PIL import Image
from turbojpeg import TurboJPEG

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


## scale jpeg by 0.5 comparison


def turbojpeg_scale(jpeg_bytes):
    # encoding BGR array to output.jpg with default settings.
    # 85=default quality
    bytes = turbojpeg.scale_with_quality(jpeg_bytes, quality=85, scaling_factor=(1, 2))

    return bytes


def pillow_scale(jpeg_bytes):
    # read image
    image = Image.open(io.BytesIO(jpeg_bytes))

    # scale by 0.5

    scale_percent = 50  # percent of original size
    width = int(image.width * scale_percent / 100)
    height = int(image.height * scale_percent / 100)
    dim = (width, height)
    # https://pillow.readthedocs.io/en/latest/handbook/concepts.html#filters-comparison-table
    image.thumbnail(dim, Image.Resampling.LANCZOS)

    # encode to jpeg again
    byte_io = io.BytesIO()
    image.save(byte_io, format="JPEG", quality=85)
    bytes_full = byte_io.getbuffer()

    return bytes_full


def cv2_scale(jpeg_bytes):
    # convert to cv2 format that can be resized by cv2
    nparr = numpy.frombuffer(jpeg_bytes, numpy.uint8)
    img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    scale_percent = 50  # percent of original size
    width = int(img_np.shape[1] * scale_percent / 100)
    height = int(img_np.shape[0] * scale_percent / 100)
    dim = (width, height)

    # resize image
    img_np_resized = cv2.resize(img_np, dim, interpolation=cv2.INTER_AREA)

    # and encode to jpeg again
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
    result, encimg = cv2.imencode(".jpg", img_np_resized, encode_param)

    return encimg


@pytest.fixture(params=["turbojpeg_scale", "pillow_scale", "cv2_scale"])
def library(request):
    # yield fixture instead return to allow for cleanup:
    yield request.param


def image(file) -> bytes:
    with open(file, "rb") as file:
        in_file_read = file.read()

    return in_file_read


@pytest.fixture()
def image_lores() -> bytes:
    yield image("tests/assets/input_lores.jpg")


@pytest.fixture()
def image_hires() -> bytes:
    yield image("tests/assets/input.jpg")


# needs pip install pytest-benchmark
@pytest.mark.benchmark(
    group="scale_lores",
)
def test_libraries_encode_lores(library, image_lores, benchmark):
    benchmark(eval(library), jpeg_bytes=image_lores)
    assert True


# needs pip install pytest-benchmark
@pytest.mark.benchmark(
    group="scale_hires",
)
def test_libraries_encode_hires(library, image_hires, benchmark):
    benchmark(eval(library), jpeg_bytes=image_hires)
    assert True
