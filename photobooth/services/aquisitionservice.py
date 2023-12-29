"""
manage up to two photobooth-app backends in this module
"""
import dataclasses
import logging
from importlib import import_module
from typing import Union

from .backends.abstractbackend import AbstractBackend
from .backends.disabled import DisabledBackend
from .backends.notavailable import NotavailableBackend
from .baseservice import BaseService
from .config import appconfig
from .config.groups.backends import EnumImageBackendsLive, EnumImageBackendsMain
from .sseservice import SseService

logger = logging.getLogger(__name__)


class AquisitionService(BaseService):

    """
    Class managing photobooth-app backends
    MAIN: used for high quality still pictures
    LIVE: used for streams and live previews
          (can be used additionally if MAIN is not capable to deliver video)
    """

    def __init__(
        self,
        sse_service: SseService,
    ):
        super().__init__(sse_service=sse_service)

        # public
        self._main_backend: AbstractBackend = None
        self._live_backend: AbstractBackend = None

    def gen_stream(self):
        """
        assigns a backend to generate a stream
        """

        if appconfig.backends.LIVEPREVIEW_ENABLED:
            if self._is_real_backend(self._live_backend):
                logger.info("livestream requested from dedicated live backend")
                return self._live_backend.gen_stream()
            elif self._is_real_backend(self._main_backend):
                logger.info("livestream requested from main backend")
                return self._main_backend.gen_stream()
            else:
                logger.error("no backend available to livestream")
                raise RuntimeError("no backend available to livestream")

        raise ConnectionRefusedError("livepreview not enabled")

    def switch_backends_to_capture_mode(self):
        """set backends to preview or capture mode (usually automatically switched as needed by processingservice)"""
        self._main_backend._on_capture_mode()
        self._live_backend._on_capture_mode()

    def switch_backends_to_preview_mode(self):
        """set backends to preview or capture mode (usually automatically switched as needed by processingservice)"""
        self._main_backend._on_preview_mode()
        self._live_backend._on_preview_mode()

    def wait_for_hq_image(self):
        """
        function blocks until high quality image is available
        """
        if self._main_backend:
            return self._main_backend.wait_for_hq_image()
        else:
            logger.error("no backend available to capture hq image")
            raise RuntimeError("no backend available to capture hq image")

    @staticmethod
    def _import_backend(backend: Union[EnumImageBackendsMain, EnumImageBackendsLive]):
        # dynamic import of backend

        module_path = f".backends.{backend.name.lower()}"
        class_name = f"{backend.value}Backend"
        pkg = ".".join(__name__.split(".")[:-1])  # to allow relative imports

        try:
            module = import_module(module_path, package=pkg)
            return getattr(module, class_name)
        except (ImportError, AttributeError) as exc:
            raise ImportError(class_name) from exc

    def start(self):
        """start backends"""

        # self.stop()

        # get backend obj and instanciate

        try:
            self._main_backend: AbstractBackend = self._import_backend(appconfig.backends.MAIN_BACKEND)()
            self._live_backend: AbstractBackend = self._import_backend(appconfig.backends.LIVE_BACKEND)()
        except Exception as exc:
            logger.exception(exc)
            logger.critical("error initializing the backends")

            self.set_status_fault()

            return

        if not self._is_real_backend(self._main_backend) and not self._is_real_backend(self._live_backend):
            logger.critical("configuration error, no backends available!")

            self.set_status_fault()

            return

        logger.info(f"aquisition main backend: {self._main_backend}")
        logger.info(f"aquisition live backend: {self._live_backend}")

        try:
            if self._main_backend:
                self._main_backend.start()
            if self._live_backend:
                self._live_backend.start()
        except Exception as exc:
            logger.exception(exc)
            logger.critical("could not init/start backend")

            self.set_status_fault()

            return

        super().set_status_started()

    def stop(self):
        """stop backends"""
        # backends stop on their own now using DI framework

        try:
            if self._main_backend:
                self._main_backend.stop()
            if self._live_backend:
                self._live_backend.stop()
        except Exception as exc:
            logger.exception(exc)
            logger.critical("could not stop backend")

        super().set_status_stopped()

    def stats(self):
        """
        Gather stats from active backends.
        Backend stats are converted to dict to be processable by JSON lib

        Returns:
            _type_: _description_
        """
        stats_primary = dataclasses.asdict(self._main_backend.stats()) if self._is_real_backend(self._main_backend) else {}
        stats_secondary = dataclasses.asdict(self._live_backend.stats()) if self._is_real_backend(self._live_backend) else {}

        aquisition_stats = {"primary": stats_primary, "secondary": stats_secondary}

        return aquisition_stats

    @staticmethod
    def _is_real_backend(backend):
        return backend is not None and not isinstance(backend, (DisabledBackend, NotavailableBackend))
