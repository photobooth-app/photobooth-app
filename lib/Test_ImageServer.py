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


def test_getImages():
    from pymitter import EventEmitter
    from PIL import Image
    import io
    import platform

    testbackends: list[ImageServerAbstract] = []

    # ImageServerSimulated backend: test on every platform
    from ImageServerSimulated import ImageServerSimulated
    testbackends.append(ImageServerSimulated(EventEmitter()))

    # ImageServerSimulated backend: test on every platform but with specific settings for windows (digicamcontrol)/linux(gphoto2)
    from ImageServerCmd import ImageServerCmd
    # TODO: find way to inject test settings to imgservcmd
    # testbackends.append(ImageServerCmd(EventEmitter()))
    logger.warning(
        "Currently not testing CMD backend, needs additional work!")

    # ImageServerPicam2 backend: test on linux/raspberry pi only:
    if platform.system() == "Linux":
        from ImageServerPicam2 import ImageServerPicam2
        testbackends.append(ImageServerPicam2(EventEmitter()))
    else:
        logger.warning("not on linux, test of Picam2 backend skipped")

    logger.debug(f"testing following backends: {testbackends}")
    for imageServerBackend in testbackends:
        logger.info(f"testing backend {imageServerBackend.__module__}")
        imageServerBackend.start()

        if imageServerBackend.providesStream:
            try:
                with Image.open(io.BytesIO(imageServerBackend._wait_for_lores_image())) as im:
                    im.verify()
            except NotImplementedError:
                raise AssertionError(
                    "backend did not return valid image bytes")

        imageServerBackend.trigger_hq_capture()
        # time.sleep(1) #TODO: race condition?!

        try:
            with Image.open(io.BytesIO(imageServerBackend.wait_for_hq_image())) as im:
                im.verify()
        except Exception as e:
            raise AssertionError(
                f"backend did not return valid image bytes {e}")

        imageServerBackend.stop()


if __name__ == '__main__':
    # setup for testing.

    # test()
    pass
