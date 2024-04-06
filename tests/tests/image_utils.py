import logging
import subprocess

import pytest
from PIL import Image, ImageChops

from photobooth.services.config import appconfig


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


logger = logging.getLogger(name=None)


def is_same(img1: Image.Image, img2: Image.Image):
    # ensure rgb for both before compare, kind of ignore transparency.
    img1 = img1.convert("RGB")
    img2 = img2.convert("RGB")

    # img1.show()
    # img2.show()

    diff = ImageChops.difference(img2, img1)
    logger.info(diff.getbbox())

    # getbbox returns None if all same, otherwise anything that is evalued to false
    return not bool(diff.getbbox())


def video_duration(input_video):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_video],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(result.stdout)
    return float(result.stdout)
