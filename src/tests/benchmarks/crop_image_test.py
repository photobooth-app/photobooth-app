import io
import logging
from collections.abc import Generator

import cv2
import numpy
import pytest
from PIL import Image
from turbojpeg import TurboJPEG

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


def turbojpeg_crop(jpeg_bytes, tmp_path):
    bytes = turbojpeg.crop(jpeg_bytes, 8, 8, 64, 64, copynone=True)

    return bytes


def pillow_crop(jpeg_bytes, tmp_path):
    # read image
    image = Image.open(io.BytesIO(jpeg_bytes))

    # scale by 0.5

    image = image.crop((8, 8, 64, 64))

    # encode to jpeg again
    byte_io = io.BytesIO()
    image.save(byte_io, format="JPEG", quality=85)
    bytes_full = byte_io.getbuffer()

    return bytes_full


def cv2_crop(jpeg_bytes, tmp_path):
    # convert to cv2 format that can be resized by cv2
    nparr = numpy.frombuffer(jpeg_bytes, numpy.uint8)
    img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    cropped_img = img_np[8 : 8 + 64, 8 : 8 + 64]

    # and encode to jpeg again
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
    result, encimg = cv2.imencode(".jpg", cropped_img, encode_param)

    return encimg.tobytes()


@pytest.fixture(
    params=[
        "turbojpeg_crop",
        "pillow_crop",
        "cv2_crop",
    ]
)
def library(request):
    # yield fixture instead return to allow for cleanup:
    yield request.param


def image(file) -> bytes:
    with open(file, "rb") as file:
        in_file_read = file.read()

    return in_file_read


@pytest.fixture()
def image_hires() -> Generator[bytes, None, None]:
    yield image("src/tests/assets/input.jpg")


@pytest.fixture()
def image_lores() -> Generator[bytes, None, None]:
    yield image("src/tests/assets/input_lores.jpg")


@pytest.mark.benchmark(group="cropjpeg_hires")
def test_libraries_encode_hires(library, image_hires, benchmark, tmp_path):
    benchmark(eval(library), jpeg_bytes=image_hires, tmp_path=tmp_path)
    assert True


@pytest.mark.benchmark(group="cropjpeg_lores")
def test_libraries_encode_lores(library, image_lores, benchmark, tmp_path):
    benchmark(eval(library), jpeg_bytes=image_lores, tmp_path=tmp_path)
    assert True
