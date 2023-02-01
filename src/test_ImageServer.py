import logging
from ImageServerAbstract import ImageServerAbstract

logging.basicConfig()
# get a root looger one time as this is used later for all other modules as template
logger = logging.getLogger(name=None)
# set debug on root, so all debug messages from all imported modules will be received also.
logger.setLevel("DEBUG")

# execute tests:
# _test_getImages()
logger.info("testing finished.")


def getImages(backend: ImageServerAbstract):
    from pymitter import EventEmitter
    from PIL import Image
    import io
    import platform

    logger.info(f"testing backend {backend.__module__}")
    backend.start()

    try:
        with Image.open(io.BytesIO(backend._wait_for_lores_image())) as im:
            im.verify()
    except NotImplementedError:
        raise AssertionError(
            "backend did not return valid image bytes")

    backend.trigger_hq_capture()
    # time.sleep(1) #TODO: race condition?!

    try:
        with Image.open(io.BytesIO(backend.wait_for_hq_image())) as im:
            im.verify()
    except Exception as e:
        raise AssertionError(
            f"backend did not return valid image bytes {e}")

    backend.stop()
