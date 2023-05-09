"""Containers module."""


import logging

from dependency_injector import containers, providers
from pymitter import EventEmitter

from .aquisitionservice import AquisitionService
from .informationservice import InformationService
from .keyboardservice import KeyboardService
from .mediacollectionservice import MediacollectionService
from .processingservice import ProcessingService
from .systemservice import SystemService
from .wledservice import WledService

logger = logging.getLogger(__name__)


def init_aquisition_resource(evtbus, LIVEPREVIEW_ENABLED, primary, secondary):
    resource = AquisitionService(
        evtbus=evtbus,
        primary=primary,
        secondary=secondary,
        LIVEPREVIEW_ENABLED=LIVEPREVIEW_ENABLED,
    )
    try:
        resource.start()
    except Exception as exc:
        logger.critical(f"failed to start acquisition {exc}")
    else:
        yield resource
    finally:
        resource.stop()


def init_information_resource(evtbus):
    resource = InformationService(evtbus=evtbus)
    resource.start()
    yield resource
    resource.stop()


def init_wled_resource(evtbus, enabled, serial_port):
    resource = WledService(evtbus=evtbus, enabled=enabled, serial_port=serial_port)
    try:
        resource.start()
    except RuntimeError as wledservice_exc:
        # catch exception to make app continue without wled service in case there is a connection problem
        logging.warning(f"WLED module init failed {wledservice_exc}")
    yield resource
    resource.stop()


class ServicesContainer(containers.DeclarativeContainer):
    evtbus = providers.Dependency(instance_of=EventEmitter)
    # settings = providers.Dependency(instance_of=AppConfig)
    # config = providers.Dependency()
    config = providers.Configuration()

    backends = providers.DependenciesContainer()

    # Services: Core
    mediacollection_service = providers.Singleton(MediacollectionService, evtbus=evtbus)

    aquisition_service = providers.Resource(
        init_aquisition_resource,
        evtbus=evtbus,
        # settings=settings,
        LIVEPREVIEW_ENABLED=config.backends.LIVEPREVIEW_ENABLED,
        primary=backends.primary_backend,
        secondary=backends.secondary_backend,
    )

    information_service = providers.Resource(init_information_resource, evtbus=evtbus)

    keyboard_service = providers.Factory(KeyboardService, evtbus=evtbus, config=config)

    processing_service = providers.Singleton(
        ProcessingService,
        evtbus=evtbus,
        aquisition_service=aquisition_service,
        mediacollection_service=mediacollection_service,
    )

    system_service = providers.Factory(SystemService, evtbus=evtbus)

    wled_service = providers.Resource(
        init_wled_resource,
        evtbus=evtbus,
        enabled=config.wled.ENABLED,
        serial_port=config.wled.SERIAL_PORT,
    )
