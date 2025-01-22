import logging

from .services.aquisition import AquisitionService
from .services.base import BaseService
from .services.collection import MediacollectionService
from .services.filtetransfer import FileTransferService
from .services.gpio import GpioService
from .services.information import InformationService
from .services.logging import LoggingService
from .services.processing import ProcessingService
from .services.qrshare import QrShareService
from .services.share import ShareService
from .services.sse import SseService
from .services.system import SystemService
from .services.wled import WledService

logger = logging.getLogger(__name__)


# and as globals module:
class Container:
    sse_service: SseService = SseService()

    logging_service: LoggingService = LoggingService(
        sse_service,
    )
    wled_service: WledService = WledService(
        sse_service,
    )
    aquisition_service: AquisitionService = AquisitionService(
        sse_service,
        wled_service,
    )
    mediacollection_service: MediacollectionService = MediacollectionService(
        sse_service,
    )
    information_service: InformationService = InformationService(
        sse_service,
        aquisition_service,
    )

    processing_service = ProcessingService(
        sse_service,
        aquisition_service,
        mediacollection_service,
        wled_service,
        information_service,
    )
    system_service = SystemService(
        sse_service,
    )
    share_service = ShareService(
        sse_service,
    )
    gpio_service = GpioService(
        sse_service,
        processing_service,
        share_service,
        mediacollection_service,
    )
    qr_share_service = QrShareService(
        sse_service,
        mediacollection_service,
    )
    filetransfer_service = FileTransferService(
        sse_service,
    )

    def _service_list(self) -> list[BaseService]:
        # list used to start/stop services. List sorted in the order of definition.
        return [getattr(self, attr) for attr in __class__.__dict__ if isinstance(getattr(self, attr), BaseService)]

    def start(self):
        for service in self._service_list():
            try:
                service.start()

                logger.info(f"started {service.__class__.__name__}")
            except Exception as exc:
                logger.exception(exc)
                logger.critical("could not start service")

        logger.info("started container")

    def stop(self):
        for service in reversed(self._service_list()):
            try:
                service.stop()

                logger.info(f"stopped {service.__class__.__name__}")
            except Exception as exc:
                logger.exception(exc)
                logger.critical("could not stop service")


container = Container()
