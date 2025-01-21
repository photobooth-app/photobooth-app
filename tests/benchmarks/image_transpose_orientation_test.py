import io
import logging

import piexif
import pytest
from PIL import Image, ImageOps
from turbojpeg import TurboJPEG

turbojpeg = TurboJPEG()
logger = logging.getLogger(name=None)

# To rotate images efficiently without reprocessing, the consuming device (browser, PIL lib, ...) need to respect the orientation
# that was set in the exif tags.
# See more references here:
# https://stackoverflow.com/a/61196140
# https://image-orientation-test.vercel.app/
# Nowadays browser support the exif orientation and it is enabled by default. So, should be safe to use.
# So this means,
# 1) we need to transpose the images in the libs and remove the exif tags or
# 2) need to ensure the exif tag is always transplanted in to the images


def transpose_pillow():
    # read image
    with Image.open("tests/assets/input_lores.jpg") as img:
        ImageOps.exif_transpose(img, in_place=True)  # needed to allow all backends set the orientation properly

    return img


def transpose_piexif():
    with open("tests/assets/input_lores.jpg", "rb") as img:
        jpeg_bytes = img.read()

    bytes = jpeg_bytes  # copy so we have an out-bytes to transplant to
    out = io.BytesIO()
    piexif.transplant(jpeg_bytes, bytes, out)

    return out.getvalue()


@pytest.mark.benchmark(group="transpose")
def test_transpose_pillow(benchmark):
    benchmark(transpose_pillow)


@pytest.mark.benchmark(group="transpose")
def test_transpose_piexif(benchmark):
    benchmark(transpose_piexif)
