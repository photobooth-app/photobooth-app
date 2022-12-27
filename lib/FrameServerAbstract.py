from abc import ABC, abstractmethod
import logging
logger = logging.getLogger(__name__)


class FrameServerAbstract(ABC):
    @abstractmethod
    def __init__(self, ee):

        self._ee = ee
        print("init abstract")
        # when countdown starts change mode to HQ. after picture was taken change back.
        self._ee.on("statemachine/armed",
                    self._onCaptureMode)

        self._ee.on("onCaptureMode", self._onCaptureMode)
        self._ee.on("onPreviewMode", self._onPreviewMode)

        super().__init__()

    @abstractmethod
    def gen_stream(self):
        pass

    @abstractmethod
    def trigger_hq_capture(self):
        pass

    @abstractmethod
    def wait_for_hq_image(self):
        pass

    @abstractmethod
    def get_metadata(self):
        pass

    @abstractmethod
    def _onCaptureMode(self):
        pass

    @abstractmethod
    def _onPreviewMode(self):
        pass
