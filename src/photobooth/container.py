import logging
from threading import Lock

from .services.acquisition import AcquisitionService
from .services.base import BaseService
from .services.collection import MediacollectionService
from .services.configuration import ConfigurationService
from .services.filtetransfer import FileTransferService
from .services.gpio import GpioService
from .services.information import InformationService
from .services.logging import LoggingService
from .services.pluginmanager import PluginManagerService
from .services.processing import ProcessingService
from .services.qrshare import QrShareService
from .services.share import ShareService
from .services.system import SystemService

logger = logging.getLogger(__name__)


# and as globals module:
class Container:
    logging_service = LoggingService()
    pluginmanager_service = PluginManagerService()

    acquisition_service = AcquisitionService()
    mediacollection_service = MediacollectionService()
    information_service = InformationService(acquisition_service)
    processing_service = ProcessingService(acquisition_service, mediacollection_service, information_service)
    system_service = SystemService()
    share_service = ShareService()
    gpio_service = GpioService(processing_service, share_service, mediacollection_service)
    qr_share_service = QrShareService(mediacollection_service)
    filetransfer_service = FileTransferService()
    config_service = ConfigurationService(pluginmanager_service)

    _lock_startstop = Lock()
    _lock_reload = Lock()
    _container_started: bool = False

    def _service_list(self) -> list[BaseService]:
        # list used to start/stop services. List sorted in the order of definition.
        return [getattr(self, attr) for attr in __class__.__dict__ if isinstance(getattr(self, attr), BaseService)]

    def start(self):
        services_started = []

        with self._lock_startstop:
            if self.is_started():
                raise RuntimeError("Service already started")

            for service in self._service_list():
                try:
                    service.start()
                    services_started.append(f"{service.__class__.__name__}: {service.get_status().name}")

                except Exception as exc:
                    logger.exception(exc)
                    logger.critical("could not start service")

            self._container_started = True

            logger.info(f"services status: {services_started}")
            logger.info("started container")

    def stop(self):
        services_stopped = []

        with self._lock_startstop:
            if not self.is_started():
                raise RuntimeError("Service already stopped")

            for service in reversed(self._service_list()):
                try:
                    service.stop()

                    services_stopped.append(f"{service.__class__.__name__}: {service.get_status().name}")
                except Exception as exc:
                    logger.exception(exc)
                    logger.critical("could not stop service")

            self._container_started = False

            logger.info(f"services status: {services_stopped}")
            logger.info("stopped container")

    def is_started(self):
        return self._container_started

    def reload(self):
        """stop all services first (reverse order), then start them again."""
        with self._lock_reload:  # lock reload so multiple calls cannot interfere and mess with the sequence
            try:
                self.stop()
            except Exception:
                ...

            try:
                self.start()
            except Exception:
                ...


container = Container()
