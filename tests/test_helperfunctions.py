import logging
import time
import sys
import os
import io
from PIL import Image

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.imageserverabstract import ImageServerAbstract

logger = logging.getLogger(name=None)


def get_images(backend: ImageServerAbstract):
    logger.info(f"testing backend {backend.__module__}")
    backend.start()

    # wait until backends threads started properly before asking for an image
    time.sleep(5)

    try:
        with Image.open(io.BytesIO(backend._wait_for_lores_image())) as img:
            img.verify()
    except Exception as exc:
        print(exc)
        raise AssertionError("backend did not return valid image bytes") from exc

    try:
        with Image.open(io.BytesIO(backend.wait_for_hq_image())) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes {exc}") from exc

    # stop backend, ensure process is joined properly to collect coverage:
    # https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html#if-you-use-multiprocessing-process
    backend.stop()
