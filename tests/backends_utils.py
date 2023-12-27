import io
from importlib import reload

from PIL import Image

import photobooth.services.config
from photobooth.services.backends.abstractbackend import AbstractBackend

reload(photobooth.services.config)  # reset config to defaults.


def get_images(backend: AbstractBackend):
    # logger.info(f"testing backend {backend.__module__}")
    # backend.start()

    try:
        with Image.open(io.BytesIO(backend.wait_for_hq_image())) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc

    try:
        with Image.open(io.BytesIO(backend._wait_for_lores_image())) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc

    # stop backend, ensure process is joined properly to collect coverage:
    # https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html#if-you-use-multiprocessing-process
    # backend.stop()
