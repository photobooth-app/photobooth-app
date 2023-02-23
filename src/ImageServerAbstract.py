from abc import ABC, abstractmethod
import logging
logger = logging.getLogger(__name__)


class ImageServerAbstract(ABC):
    @abstractmethod
    def __init__(self, ee, enableStream):
        # public
        self.exif_make = "ImageServerAbstract-Make"
        self.exif_model = "ImageServerAbstract-Model"
        self.metadata = {}

        # private
        self._enableStream = enableStream
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

    # @property
    # @abstractmethod
    # def stream_url(self):
    #    """
    #    get the default backend stream
    #    """
    #    pass

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

    """
    INTERNAL FUNCTIONS TO BE IMPLEMENTED
    """

    @abstractmethod
    def _wait_for_lores_frame(self):
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


"""
INTERNAL FUNCTIONS to operate on the shared memory exchanged between processes.
"""


def decompileBuffer(shm: memoryview):
    # ATTENTION: shm is a memoryview; sliced variables are also a reference only.
    # means for this app in consequence: here is the place to make a copy of the image for further processing
    # ATTENTION2: this function needs to be called with lock aquired
    length = int.from_bytes(shm.buf[0:4], 'big')
    ret: memoryview = (shm.buf[4:length+4])
    return (ret.tobytes())


def compileBuffer(shm, jpeg_buffer):
    # ATTENTION: shm is a memoryview; sliced variables are also a reference only.
    # means for this app in consequence: here is the place to make a copy of the image for further processing
    # ATTENTION2: this function needs to be called with lock aquired
    length: int = len(jpeg_buffer)
    length_bytes = length.to_bytes(4, 'big')
    shm.buf[0:4] = (length_bytes)
    shm.buf[4:length+4] = (jpeg_buffer)
