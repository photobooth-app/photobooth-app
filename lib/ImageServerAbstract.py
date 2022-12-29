from abc import ABC, abstractmethod
import logging
logger = logging.getLogger(__name__)


class ImageServerAbstract(ABC):
    @abstractmethod
    def __init__(self, ee):
        # public
        self.exif_make = "ImageServerAbstract-Make"
        self.exif_model = "ImageServerAbstract-Model"
        self.metadata = {}
        self.providesStream = False

        # private
        self._fps = 0

        self._ee = ee
        self._ee.on("statemachine/armed",
                    self._onCaptureMode)

        self._ee.on("onCaptureMode", self._onCaptureMode)
        self._ee.on("onPreviewMode", self._onPreviewMode)

        super().__init__()

    @abstractmethod
    def gen_stream(self):
        """
        yield jpeg images to stream to client (if not created otherwise)
        """
        pass

    @abstractmethod
    def trigger_hq_capture(self):
        """
        trigger one time capture of high quality image
        """
        pass

    @abstractmethod
    def wait_for_hq_image(self):
        """
        function blocks until high quality image is available
        """
        pass

    @abstractmethod
    def start(self):
        """To start the backend to serve"""
        pass

    @abstractmethod
    def stop(self):
        """To stop the backend to serve"""
        pass

    @property
    @abstractmethod
    def fps(self):
        """frames per second"""
        pass

    """
    INTERNAL FUNCTIONS TO BE IMPLEMENTED
    """

    @abstractmethod
    def _wait_for_autofocus_frame(self):
        """
        function blocks until frame is available for autofocus usually
        """
        pass

    @abstractmethod
    def _onCaptureMode(self):
        """called externally via events and used to change to a capture mode if necessary"""
        pass

    @abstractmethod
    def _onPreviewMode(self):
        """called externally via events and used to change to a preview mode if necessary"""
        pass


# Test function for module
def _test():
    # setup for testing.

    logging.basicConfig()
    # get a root looger one time as this is used later for all other modules as template
    logger = logging.getLogger('root')
    # set debug on root, so all debug messages from all imported modules will be received also.
    logger.setLevel("DEBUG")

    # execute tests:
    _test_getImages()
    logger.info("testing finished.")


def _test_getImages():
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
        except:
            raise AssertionError("backend did not return valid image bytes")

        imageServerBackend.stop()


if __name__ == '__main__':
    _test()
