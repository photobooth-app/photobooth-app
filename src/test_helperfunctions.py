import logging
import time
import io
from PIL import Image
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
        print("exception!")
        print(exc)
        raise AssertionError("backend did not return valid image bytes") from exc

    backend.trigger_hq_capture()

    try:
        with Image.open(io.BytesIO(backend.wait_for_hq_image())) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes {exc}") from exc

    backend.stop()
