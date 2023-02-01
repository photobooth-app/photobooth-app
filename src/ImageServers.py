from importlib import import_module
from ConfigSettings import settings
import ImageServerAbstract
import logging
logger = logging.getLogger(__name__)


class ImageServers():

    def __init__(self, ee):
        # public
        self.primaryBackend: ImageServerAbstract = None
        self.secondaryBackend: ImageServerAbstract = None

        self.metadata = {}

        # load imageserver dynamically because service can be configured https://stackoverflow.com/a/14053838
        imageserverPrimaryBackendModule = import_module(
            f"src.{settings.backends.MAIN_BACKEND}")
        clsPrimary = getattr(imageserverPrimaryBackendModule,
                             settings.backends.MAIN_BACKEND)
        self.primaryBackend = clsPrimary(ee, False)

        # load imageserver dynamically because service can be configured https://stackoverflow.com/a/14053838
        if not settings.backends.LIVE_BACKEND == None:
            imageserverSecondaryBackendModule = import_module(
                f"src.{settings.backends.LIVE_BACKEND}")
            clsSecondary = getattr(imageserverSecondaryBackendModule,
                                   settings.backends.LIVE_BACKEND)
            self.secondaryBackend = clsSecondary(ee, True)

    def gen_stream(self):
        if settings.backends.LIVEPREVIEW_ENABLED:
            if self.secondaryBackend:
                return self.secondaryBackend.gen_stream()
            else:
                return self.primaryBackend.gen_stream()
        else:
            raise Exception("livepreview not enabled")
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
        self.primaryBackend.start()

        if self.secondaryBackend:
            self.secondaryBackend.start()

    def stop(self):
        self.primaryBackend.stop()

        if self.secondaryBackend:
            self.secondaryBackend.stop()
