"""
manage up to two photobooth-app backends in this module
"""
import dataclasses

from pymitter import EventEmitter

from ..appconfig import AppConfig
from .backends.abstractbackend import AbstractBackend
from .baseservice import BaseService


class AquisitionService(BaseService):

    """
    Class managing photobooth-app backends
    MAIN: used for high quality still pictures
    LIVE: used for streams and live previews
          (can be used additionally if MAIN is not capable to deliver video)
    """

    def __init__(
        self,
        evtbus: EventEmitter,
        primary: AbstractBackend,
        secondary: AbstractBackend,
        config: AppConfig,
    ):
        super().__init__(evtbus=evtbus, config=config)

        self._LIVEPREVIEW_ENABLED = config.backends.LIVEPREVIEW_ENABLED

        # public
        self.primary_backend: AbstractBackend = primary
        self.secondary_backend: AbstractBackend = secondary

        self.metadata = {}

        if not self.primary_backend and not self.primary_backend:
            self._logger.critical("configuration error, no backends available!")

        self._logger.info(f"init {self.primary_backend=}")
        self._logger.info(f"init {self.secondary_backend=}")

    def gen_stream(self):
        """
        assigns a backend to generate a stream
        """
        if self._LIVEPREVIEW_ENABLED:
            if self.secondary_backend:
                self._logger.info("livestream requested from secondary backend")
                return self.secondary_backend.gen_stream()
            else:
                self._logger.info("livestream requested from primary backend")
                return self.primary_backend.gen_stream()

        raise ConnectionRefusedError("livepreview not enabled")

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
        if self.primary_backend:
            self.primary_backend.start()

        if self.secondary_backend:
            self.secondary_backend.start()

        super().set_status_started()

    def stop(self):
        """stop backends"""
        if self.primary_backend:
            self.primary_backend.stop()

        if self.secondary_backend:
            self.secondary_backend.stop()

        super().set_status_stopped()

    def stats(self):
        """
        Gather stats from active backends.
        Backend stats are converted to dict to be processable by JSON lib

        Returns:
            _type_: _description_
        """
        stats_primary = dataclasses.asdict(self.primary_backend.stats())
        stats_secondary = dataclasses.asdict(self.secondary_backend.stats()) if self.secondary_backend else None

        aquisition_stats = {"primary": stats_primary, "secondary": stats_secondary}

        return aquisition_stats
