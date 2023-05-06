import logging
import io
from PIL import Image

from src.imageserverabstract import ImageServerAbstract

logger = logging.getLogger(name=None)


def get_images(backend: ImageServerAbstract):
    logger.info(f"testing backend {backend.__module__}")
    backend.start()

    try:
        with Image.open(
            io.BytesIO(
                backend._wait_for_lores_image()  # pylint:disable=protected-access
            )
        ) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(
            f"backend did not return valid image bytes, {exc}"
        ) from exc

    try:
        with Image.open(io.BytesIO(backend.wait_for_hq_image())) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(
            f"backend did not return valid image bytes, {exc}"
        ) from exc

    # stop backend, ensure process is joined properly to collect coverage:
    # https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html#if-you-use-multiprocessing-process
    backend.stop()
