import logging

import cv2
import numpy
import pytest
import pyvips
from PIL import Image, ImageOps
from turbojpeg import TurboJPEG

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


# jpegtran?
# turbojpeg (has no binding to transform)
# numpy
# cv2
# pil


def pyvips_flip(pil_image):
    lgr = logging.getLogger(name="pyvips")
    lgr.setLevel(logging.WARNING)
    lgr.propagate = True

    image = pyvips.Image.new_from_array(pil_image)
    image.fliphor()

    return Image.fromarray(image.numpy())


def numpy_flip(pil_image):
    nparr = numpy.array(pil_image)
    nparr = numpy.fliplr(nparr)
    return Image.fromarray(nparr)


def pillow_flip(pil_image):
    return ImageOps.mirror(pil_image)


def cv2_flip(pil_image):
    open_cv_image = numpy.array(pil_image)
    img_flipped = cv2.flip(open_cv_image, 1)
    flipped_pil = Image.fromarray(img_flipped)
    return flipped_pil


@pytest.fixture(params=["numpy_flip", "pillow_flip", "cv2_flip", "pyvips_flip"])
def library(request):
    # yield fixture instead return to allow for cleanup:
    yield request.param


def image(file) -> Image.Image:
    img = Image.open(file)
    img.load()
    return img


@pytest.fixture()
def image_lores() -> bytes:
    yield image("tests/assets/input_lores.jpg")


@pytest.fixture()
def image_hires() -> bytes:
    yield image("tests/assets/input.jpg")


# needs pip install pytest-benchmark
@pytest.mark.benchmark(group="flip_lores")
def test_libraries_encode_lores(library, image_lores, benchmark):
    benchmark(eval(library), pil_image=image_lores)
    assert True


# needs pip install pytest-benchmark
@pytest.mark.benchmark(group="flip_hires")
def test_libraries_encode_hires(library, image_hires, benchmark):
    benchmark(eval(library), pil_image=image_hires)
    assert True
