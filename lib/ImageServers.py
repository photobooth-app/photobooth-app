from importlib import import_module
from ConfigSettings import settings
import ImageServerAbstract
import logging
logger = logging.getLogger(__name__)


class ImageServers():

    def __init__(self, ee):
        # public
        self.main: ImageServerAbstract = None
        self.live: ImageServerAbstract = None

        self.metadata = {}

        # load imageserver dynamically because service can be configured https://stackoverflow.com/a/14053838
        imageserverModule = import_module(
            f"lib.{settings.common.IMAGESERVER_BACKEND}")
        cls = getattr(imageserverModule, settings.common.IMAGESERVER_BACKEND)
        self.main = cls(ee)

        # load imageserver dynamically because service can be configured https://stackoverflow.com/a/14053838
        imageserverLiveviewModule = import_module(
            f"lib.ImageServerSimulated")
        clsLiveview = getattr(imageserverLiveviewModule,
                              "ImageServerSimulated")
        self.live = clsLiveview(ee)

    def gen_stream(self):
        if self.live and self.live._providesStream:
            return self.live.gen_stream()
        elif self.main and self.main._providesStream:
            return self.main.gen_stream()
        else:
            raise Exception("no livestream available")

    # @property
    # @abstractmethod
    # def stream_url(self):
    #    """
    #    get the default backend stream
    #    """
    #    pass

    def trigger_hq_capture(self):
        """
        trigger one time capture of high quality image
        """
        pass

    def wait_for_hq_image(self):
        """
        function blocks until high quality image is available
        """
        pass

    def start(self):
        self.main.start()

        if self.live:
            self.live.start()

    def stop(self):
        self.main.stop()

        if self.live:
            self.live.stop()
