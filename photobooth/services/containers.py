"""Containers module."""


import logging

from dependency_injector import containers, providers

from ..appconfig import AppConfig
from .aquisitionservice import AquisitionService
from .baseservice import BaseService
from .filtetransferservice import FileTransferService
from .gpioservice import GpioService
from .informationservice import InformationService
from .keyboardservice import KeyboardService
from .mediacollectionservice import MediacollectionService
from .mediaprocessingservice import MediaprocessingService
from .printingservice import PrintingService
from .processingservice import ProcessingService
from .shareservice import ShareService
from .sseservice import SseService
from .systemservice import SystemService
from .wledservice import WledService

logger = logging.getLogger(__name__)


def init_res_obj_service(_obj_: BaseService, config: AppConfig, sse_service: SseService, *args):
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
        resource = _obj_(config, sse_service, *args)
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


class ServicesContainer(containers.DeclarativeContainer):
    config = providers.Dependency(instance_of=AppConfig)
    sse_service = providers.Dependency(instance_of=SseService)
    backends = providers.DependenciesContainer()

    # Services: Core

    aquisition_service = providers.Resource(
        init_res_obj_service,
        AquisitionService,
        config,
        sse_service,
        backends.primary_backend,
        backends.secondary_backend,
    )

    information_service = providers.Resource(
        init_res_obj_service,
        InformationService,
        config,
        sse_service,
    )

    wled_service = providers.Resource(
        init_res_obj_service,
        WledService,
        config,
        sse_service,
    )

    mediaprocessing_service = providers.Singleton(
        MediaprocessingService,
        config,
        sse_service,
    )
    mediacollection_service = providers.Singleton(
        MediacollectionService,
        config,
        sse_service,
        mediaprocessing_service,
    )

    processing_service = providers.Singleton(
        ProcessingService,
        config,
        sse_service,
        aquisition_service,
        mediacollection_service,
        mediaprocessing_service,
        wled_service,
    )

    system_service = providers.Factory(
        SystemService,
        config,
        sse_service,
    )

    printing_service = providers.Resource(
        init_res_obj_service,
        PrintingService,
        config,
        sse_service,
        mediacollection_service,
    )

    keyboard_service = providers.Resource(
        init_res_obj_service,
        KeyboardService,
        config,
        sse_service,
        processing_service,
        printing_service,
        mediacollection_service,
    )

    gpio_service = providers.Resource(
        init_res_obj_service,
        GpioService,
        config,
        sse_service,
        processing_service,
        printing_service,
        mediacollection_service,
    )

    share_service = providers.Resource(
        init_res_obj_service,
        ShareService,
        config,
        sse_service,
        mediacollection_service,
    )

    filetransfer_service = providers.Resource(
        init_res_obj_service,
        FileTransferService,
        config,
        sse_service,
    )
