"""Dependencies definition.

3 levels of dependencies:
  - app: FastAPI(dependencies=[Depends() ...])
  - route: APIRouter(dependencies=[Depends() ...])
  - endpoint: add Depends to endpoint.

Extra:
  - appconfig as global module (similar as logging module a global module that keeps the one instance of the appconfig.)
"""


import contextlib
import logging.config

import inject
from dependency_injector import containers, providers

from .services.aquisitionservice import AquisitionService
from .services.baseservice import BaseService
from .services.filtetransferservice import FileTransferService
from .services.gpioservice import GpioService
from .services.informationservice import InformationService
from .services.keyboardservice import KeyboardService
from .services.loggingservice import LoggingService
from .services.mediacollectionservice import MediacollectionService
from .services.mediaprocessingservice import MediaprocessingService
from .services.printingservice import PrintingService
from .services.processingservice import ProcessingService
from .services.shareservice import ShareService
from .services.sseservice import SseService
from .services.systemservice import SystemService
from .services.wledservice import WledService

logger = logging.getLogger(__name__)


def init_res_obj_service(_obj_: BaseService, sse_service: SseService, *args):
    """Initialize services as ressources.
    Ensure to no reraise exceptions, so only the service will fail instead the
    whole app crash because of exception not catched

    Args:
        _obj_ (BaseService): Class of type BaseService or derived from that
        config (AppConfig): Instance of config
        sse_service (sse_service)

    Yields:
        _obj_: Initialized resource (inherited from BaseService)
    """
    resource = None

    try:
        resource: BaseService = _obj_(sse_service, *args)
        resource.start()
    except Exception as exc:
        logger.exception(exc)
        logger.critical("could not init/start resource")
    finally:
        yield resource

    try:
        if resource:  # if not none
            resource.stop()
    except Exception as exc:
        logger.exception(exc)
        logger.critical("could not stop resource")


# Dependencies
@contextlib.contextmanager
def get_sse_service():
    sse_service = SseService()
    print("start sse")
    # setup
    try:
        print("yield sse")
        yield sse_service
    finally:
        print("stop sse")
        pass  # terminate


@contextlib.contextmanager
@inject.params(sse_service=SseService)
def get_logging_service(sse_service: SseService = None):
    logging_service = LoggingService(sse_service=sse_service)
    print("init log")
    try:
        logging_service.start()
        print("start log")
        yield logging_service
    finally:
        print("stop log")
        logging_service.stop()


# Create an optional configuration.
def my_config(binder):
    binder.bind_to_provider(SseService, get_sse_service)
    binder.bind_to_provider(LoggingService, get_logging_service)


# Configure a shared injector.
inject.configure(my_config)


@inject.autoparams()
def useItExample(logger: LoggingService, sse: SseService):
    # Connection and file will be automatically destroyed on exit.
    print(sse.dispatch_event("test"))
    pass


# useItExample()


class ServicesContainer(containers.DeclarativeContainer):
    sse_service = providers.Singleton(SseService)

    logging_service = providers.Resource(
        LoggingService,
        sse_service=sse_service,
    )

    # Services: Core

    aquisition_service = providers.Resource(
        init_res_obj_service,
        AquisitionService,
        sse_service,
    )

    information_service = providers.Resource(
        init_res_obj_service,
        InformationService,
        sse_service,
        aquisition_service,
    )

    wled_service = providers.Resource(
        init_res_obj_service,
        WledService,
        sse_service,
    )

    mediaprocessing_service = providers.Singleton(
        MediaprocessingService,
        sse_service,
    )
    mediacollection_service = providers.Singleton(
        MediacollectionService,
        sse_service,
        mediaprocessing_service,
    )

    processing_service = providers.Singleton(
        ProcessingService,
        sse_service,
        aquisition_service,
        mediacollection_service,
        mediaprocessing_service,
        wled_service,
    )

    system_service = providers.Factory(
        SystemService,
        sse_service,
    )

    printing_service = providers.Resource(
        init_res_obj_service,
        PrintingService,
        sse_service,
        mediacollection_service,
    )

    keyboard_service = providers.Resource(
        init_res_obj_service,
        KeyboardService,
        sse_service,
        processing_service,
        printing_service,
        mediacollection_service,
    )

    gpio_service = providers.Resource(
        init_res_obj_service,
        GpioService,
        sse_service,
        processing_service,
        printing_service,
        mediacollection_service,
    )

    share_service = providers.Resource(
        init_res_obj_service,
        ShareService,
        sse_service,
        mediacollection_service,
    )

    filetransfer_service = providers.Resource(
        init_res_obj_service,
        FileTransferService,
        sse_service,
    )


class ApplicationContainer(containers.DeclarativeContainer):
    services = providers.Container(
        ServicesContainer,
    )
