"""
manage up to two photobooth-app backends in this module
"""
import dataclasses

from ..appconfig import AppConfig
from .backends.abstractbackend import AbstractBackend
from .baseservice import BaseService
from .sseservice import SseService


class AquisitionService(BaseService):

    """
    Class managing photobooth-app backends
    MAIN: used for high quality still pictures
    LIVE: used for streams and live previews
          (can be used additionally if MAIN is not capable to deliver video)
    """

    def __init__(
        self,
        config: AppConfig,
        sse_service: SseService,
        primary_backend: AbstractBackend,
        secondary_backend: AbstractBackend,
    ):
        super().__init__(config=config, sse_service=sse_service)

        self._LIVEPREVIEW_ENABLED = config.backends.LIVEPREVIEW_ENABLED

        # public
        self.primary_backend: AbstractBackend = primary_backend
        self.secondary_backend: AbstractBackend = secondary_backend

        self.metadata = {}

        self._logger.info(f"init {self.primary_backend=}")
        self._logger.info(f"init {self.secondary_backend=}")

        if not self.primary_backend and not self.primary_backend:
            self._logger.critical("configuration error, no backends available!")

    def gen_stream(self):
        """
        assigns a backend to generate a stream
        """
        if self._LIVEPREVIEW_ENABLED:
            if self.secondary_backend:
                self._logger.info("livestream requested from secondary backend")
                return self.secondary_backend.gen_stream()
            elif self.primary_backend:
                self._logger.info("livestream requested from primary backend")
                return self.primary_backend.gen_stream()
            else:
                self._logger.error("no backend available to livestream")
                raise RuntimeError("no backend available to livestream")

        raise ConnectionRefusedError("livepreview not enabled")

    def switch_backends_to_capture_mode(self):
        """set backends to preview or capture mode (usually automatically switched as needed by processingservice)"""
        self.primary_backend._on_capture_mode()
        if self.secondary_backend:
            self.secondary_backend._on_capture_mode()

    def switch_backends_to_preview_mode(self):
        """set backends to preview or capture mode (usually automatically switched as needed by processingservice)"""
        self.primary_backend._on_preview_mode()
        if self.secondary_backend:
            self.secondary_backend._on_preview_mode()

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
        if self.primary_backend:
            return self.primary_backend.wait_for_hq_image()
        else:
            self._logger.error("no backend available to capture hq image")
            raise RuntimeError("no backend available to capture hq image")

    def start(self):
        """start backends"""
        # backends start on their own now using DI framework

        super().set_status_started()

    def stop(self):
        """stop backends"""
        # backends stop on their own now using DI framework

        super().set_status_stopped()

    def stats(self):
        """
        Gather stats from active backends.
        Backend stats are converted to dict to be processable by JSON lib

        Returns:
            _type_: _description_
        """
        stats_primary = dataclasses.asdict(self.primary_backend.stats()) if self.primary_backend else None
        stats_secondary = dataclasses.asdict(self.secondary_backend.stats()) if self.secondary_backend else None

        aquisition_stats = {"primary": stats_primary, "secondary": stats_secondary}

        return aquisition_stats
