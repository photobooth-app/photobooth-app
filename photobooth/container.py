import logging

from .services.aquisitionservice import AquisitionService
from .services.baseservice import BaseService
from .services.filtetransferservice import FileTransferService
from .services.gpioservice import GpioService
from .services.informationservice import InformationService
from .services.loggingservice import LoggingService
from .services.mediacollectionservice import MediacollectionService
from .services.mediaprocessingservice import MediaprocessingService
from .services.processingservice import ProcessingService
from .services.qrshareservice import QrShareService
from .services.shareservice import ShareService
from .services.sseservice import SseService
from .services.systemservice import SystemService
from .services.wledservice import WledService

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
    mediaprocessing_service: MediaprocessingService = MediaprocessingService(
        sse_service,
    )
    mediacollection_service: MediacollectionService = MediacollectionService(
        sse_service,
        mediaprocessing_service,
    )
    information_service: InformationService = InformationService(
        sse_service,
        aquisition_service,
    )

    processing_service = ProcessingService(
        sse_service,
        aquisition_service,
        mediacollection_service,
        mediaprocessing_service,
        wled_service,
        information_service,
    )
    system_service = SystemService(
        sse_service,
    )
    share_service = ShareService(
        sse_service,
        mediacollection_service,
        information_service,
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
