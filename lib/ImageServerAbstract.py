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
    def _onCaptureMode(self):
        """called externally via events and used to change to a capture mode if necessary"""
        pass

    @abstractmethod
    def _onPreviewMode(self):
        """called externally via events and used to change to a preview mode if necessary"""
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
