"""Containers module."""


import logging

from dependency_injector import containers, providers
from pymitter import EventEmitter

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


def init_res_obj_service(_obj_: BaseService, evtbus: EventEmitter, config: AppConfig, *args):
    """Initialize services as ressources.
    Ensure to no reraise exceptions, so only the service will fail instead the
    whole app crash because of exception not catched

    Args:
        _obj_ (BaseService): Class of type BaseService or derived from that
        evtbus (EventEmitter): Instance of eventbus
        config (AppConfig): Instance of config

    Yields:
        _obj_: Initialized resource (inherited from BaseService)
    """
    resource = None

    try:
        resource = _obj_(evtbus, config, *args)
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
    evtbus = providers.Dependency(instance_of=EventEmitter)
    config = providers.Dependency(instance_of=AppConfig)
    backends = providers.DependenciesContainer()

    # Services: Core

    sse_service = providers.Singleton(
        SseService,
        evtbus,
        config,
    )

    aquisition_service = providers.Resource(
        init_res_obj_service,
        AquisitionService,
        evtbus,
        config,
        backends.primary_backend,
        backends.secondary_backend,
    )

    information_service = providers.Resource(
        init_res_obj_service,
        InformationService,
        evtbus,
        config,
    )

    mediaprocessing_service = providers.Singleton(
        MediaprocessingService,
        evtbus,
        config,
    )
    mediacollection_service = providers.Singleton(
        MediacollectionService,
        evtbus,
        config,
        mediaprocessing_service,
    )

    processing_service = providers.Singleton(
        ProcessingService,
        evtbus,
        config,
        aquisition_service,
        mediacollection_service,
        mediaprocessing_service,
    )

    system_service = providers.Factory(
        SystemService,
        evtbus,
        config,
    )

    wled_service = providers.Resource(
        init_res_obj_service,
        WledService,
        evtbus,
        config,
    )

    printing_service = providers.Resource(
        init_res_obj_service,
        PrintingService,
        evtbus,
        config,
        mediacollection_service,
    )

    keyboard_service = providers.Resource(
        init_res_obj_service,
        KeyboardService,
        evtbus,
        config,
        processing_service,
        printing_service,
        mediacollection_service,
    )

    gpio_service = providers.Resource(
        init_res_obj_service,
        GpioService,
        evtbus,
        config,
        processing_service,
        printing_service,
        mediacollection_service,
    )

    share_service = providers.Resource(
        init_res_obj_service,
        ShareService,
        evtbus,
        config,
        mediacollection_service,
    )

    filetransfer_service = providers.Resource(
        init_res_obj_service,
        FileTransferService,
        evtbus,
        config,
    )
