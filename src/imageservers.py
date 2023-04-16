"""
manage up to two imageserver backends in this module
"""
import logging
import dataclasses
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

        # logic to determine backends to load and which whether to enable stream
        load_secondary_backend = (
            settings.backends.LIVEPREVIEW_ENABLED
            and settings.backends.LIVE_BACKEND
            and not settings.backends.LIVE_BACKEND == EnumImageBackendsLive.NULL
            and settings.backends.LIVE_BACKEND.value
        )
        enable_stream_on_primary = (
            not load_secondary_backend and settings.backends.LIVEPREVIEW_ENABLED
        )
        logger.info(f"{load_secondary_backend=}, {enable_stream_on_primary=}")

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
        self.primary_backend = cls_primary(evtbus, enable_stream_on_primary)

        # load imageserver dynamically because service can
        # be configured https://stackoverflow.com/a/14053838
        if load_secondary_backend:
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
            return (
                self.secondary_backend.gen_stream()
                if self.secondary_backend
                else self.primary_backend.gen_stream()
            )

        raise RuntimeError("livepreview not enabled")

    # @property
    # @abstractmethod
    # def stream_url(self):
    #    """
    #    get the default backend stream
    #    """
    #    pass

    def wait_for_hq_image(self):
        """
        function blocks until high quality image is available
        """
        return self.primary_backend.wait_for_hq_image()

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

    def stats(self):
        """
        Gather stats from active backends.
        Backend stats are converted to dict to be processable by JSON lib

        Returns:
            _type_: _description_
        """
        stats_primary = dataclasses.asdict(self.primary_backend.stats())
        stats_secondary = (
            dataclasses.asdict(self.secondary_backend.stats())
            if self.secondary_backend
            else None
        )

        imageservers_stats = {"primary": stats_primary, "secondary": stats_secondary}

        # logger.debug(f"{imageservers_stats=}")

        return imageservers_stats
