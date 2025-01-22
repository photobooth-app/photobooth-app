import logging

import pytest
from PIL import Image
from turbojpeg import TurboJPEG

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)


def get_dimensions_pillow():
    # read image
    with Image.open("src/tests/assets/input_lores.jpg") as img:
        width, height = img.size

    return (width, height)


def get_dimensions_turbojpeg():
    with open("src/tests/assets/input_lores.jpg", "rb") as file:
        in_file_read = file.read()
        (width, height, _, _) = turbojpeg.decode_header(in_file_read)

    return (width, height)


@pytest.mark.benchmark(group="getdimension")
def test_dimensions_pillow_load(benchmark):
    assert get_dimensions_pillow() == (1280, 800)
    benchmark(get_dimensions_pillow)


@pytest.mark.benchmark(group="getdimension")
def test_dimensions_turbojpeg(benchmark):
    assert get_dimensions_turbojpeg() == (1280, 800)
    benchmark(get_dimensions_turbojpeg)
