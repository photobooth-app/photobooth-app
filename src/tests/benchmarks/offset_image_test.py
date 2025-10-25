import logging

import pytest
from PIL import Image, ImageChops

logger = logging.getLogger(name=None)


def recenter_image(img: Image.Image, offset: tuple[int, int]):
    dx, dy = offset
    out = Image.new(img.mode, img.size, (0, 0, 0))  # black background
    out.paste(img, (-dx, -dy))
    return out


def recenter_image_chops(img, offset: tuple[int, int]):
    dx, dy = offset
    return ImageChops.offset(img, -dx, -dy)


@pytest.fixture()
def image_hires_rgb():
    yield Image.new("RGB", (1920, 1020), "red")


@pytest.mark.benchmark(group="offset_image")
def test_recenter_image(image_hires_rgb, benchmark):
    benchmark(recenter_image, image_hires_rgb, (100, 20))


@pytest.mark.benchmark(group="offset_image")
def test_recenter_image_chops(image_hires_rgb, benchmark):
    benchmark(recenter_image_chops, image_hires_rgb, (100, 20))
