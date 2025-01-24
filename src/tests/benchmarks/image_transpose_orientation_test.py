import io
import logging

import piexif
import pytest
from PIL import Image, ImageOps
from turbojpeg import TurboJPEG

from ..tests.util import get_exiforiented_jpeg, get_jpeg

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


def transpose_pillow(jpg_with_exif_data):
    # read image
    with Image.open(jpg_with_exif_data) as img:
        ImageOps.exif_transpose(img, in_place=True)  # needed to allow all backends set the orientation properly

    return img


def transpose_piexif(jpg_with_exif_data):
    bytes = jpg_with_exif_data  # copy so we have an out-bytes to transplant to
    out = io.BytesIO()
    piexif.transplant(jpg_with_exif_data, bytes, out)

    return out.getvalue()


@pytest.mark.benchmark(group="transpose")
def test_transpose_pillow(benchmark):
    jpeg_bytes_io = get_jpeg((1800, 700))
    updated_jpeg_bytes_io = get_exiforiented_jpeg(jpeg_bytes_io, 5)
    benchmark(transpose_pillow, updated_jpeg_bytes_io)


@pytest.mark.benchmark(group="transpose")
def test_transpose_piexif(benchmark):
    jpeg_bytes_io = get_jpeg((1800, 700))
    updated_jpeg_bytes_io = get_exiforiented_jpeg(jpeg_bytes_io, 5)
    benchmark(transpose_piexif, updated_jpeg_bytes_io.getvalue())
