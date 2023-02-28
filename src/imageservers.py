"""
manage up to two imageserver backends in this module
"""
import logging
from importlib import import_module
from pymitter import EventEmitter
from src.configsettings import settings, EnumImageBackendsLive
from src.imageserverabstract import ImageServerAbstract

logger = logging.getLogger(__name__)


class ImageServers:
    """
    Class managing imageserver backends
    MAIN: used for high quality still pictures
    LIVE: used for streams and live previews
          (can be used additionally if MAIN is not capable to deliver video)
    """

    def __init__(self, evtbus: EventEmitter):
        # public
        self.primary_backend: ImageServerAbstract = None
        self.secondary_backend: ImageServerAbstract = None

        self.metadata = {}

        # load imageserver dynamically because service can
        # be configured https://stackoverflow.com/a/14053838
        logger.info(
            f"loading primary backend: src.{settings.backends.MAIN_BACKEND.value}"
        )
        imageserver_primary_backendmodule = import_module(
            f"src.{settings.backends.MAIN_BACKEND.lower()}"
        )
        cls_primary = getattr(
            imageserver_primary_backendmodule, settings.backends.MAIN_BACKEND.value
        )
        self.primary_backend = cls_primary(evtbus, False)

        # load imageserver dynamically because service can
        # be configured https://stackoverflow.com/a/14053838
        if (
            settings.backends.LIVE_BACKEND
            and not settings.backends.LIVE_BACKEND == EnumImageBackendsLive.NULL
            and settings.backends.LIVE_BACKEND.value
        ):
            logger.info(
                f"loading secondary backend: src.{settings.backends.LIVE_BACKEND.value}"
            )
            imageserver_secondary_backendmodule = import_module(
                f"src.{settings.backends.LIVE_BACKEND.lower()}"
            )
            cls_secondary = getattr(
                imageserver_secondary_backendmodule,
                settings.backends.LIVE_BACKEND.value,
            )
            self.secondary_backend = cls_secondary(evtbus, True)

    def gen_stream(self):
        """
        assigns a backend to generate a stream
        """
        if settings.backends.LIVEPREVIEW_ENABLED:
            if self.secondary_backend:
                return self.secondary_backend.gen_stream()

            return self.primary_backend.gen_stream()
        else:
            raise IOError("livepreview not enabled")

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

    def wait_for_hq_image(self):
        """
        function blocks until high quality image is available
        """

    def start(self):
        """start backends"""
        self.primary_backend.start()

        if self.secondary_backend:
            self.secondary_backend.start()

    def stop(self):
        """stop backends"""
        self.primary_backend.stop()

        if self.secondary_backend:
            self.secondary_backend.stop()
