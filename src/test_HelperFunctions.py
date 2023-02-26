import logging
import time
from ImageServerAbstract import ImageServerAbstract

logger = logging.getLogger(name=None)


def getImages(backend: ImageServerAbstract):
    from pymitter import EventEmitter
    from PIL import Image
    import io
    import platform

    logger.info(f"testing backend {backend.__module__}")
    backend.start()

    # wait until backends threads started properly before asking for an image
    time.sleep(5)

    try:
        with Image.open(io.BytesIO(backend._wait_for_lores_image())) as im:
            im.verify()
    except Exception as e:
        print("exception!")
        print(e)
        raise AssertionError(
            "backend did not return valid image bytes")

    backend.trigger_hq_capture()

    try:
        with Image.open(io.BytesIO(backend.wait_for_hq_image())) as im:
            im.verify()
    except Exception as e:
        raise AssertionError(
            f"backend did not return valid image bytes {e}")

    backend.stop()
