import io

import pytest
from PIL import Image

from photobooth.services.backends.abstractbackend import AbstractBackend
from photobooth.services.config import appconfig


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


def get_images(backend: AbstractBackend):
    # logger.info(f"testing backend {backend.__module__}")
    # backend.start()

    try:
        with Image.open(io.BytesIO(backend.wait_for_hq_image())) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc

    try:
        with Image.open(io.BytesIO(backend.wait_for_lores_image())) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc

    # stop backend, ensure process is joined properly to collect coverage:
    # https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html#if-you-use-multiprocessing-process
    # backend.stop()
