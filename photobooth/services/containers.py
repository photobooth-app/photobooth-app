"""Containers module."""


import logging

from dependency_injector import containers, providers
from pymitter import EventEmitter

from ..appconfig import AppConfig
from .aquisitionservice import AquisitionService
from .informationservice import InformationService
from .keyboardservice import KeyboardService
from .mediacollectionservice import MediacollectionService
from .processingservice import ProcessingService
from .systemservice import SystemService
from .wledservice import WledService

logger = logging.getLogger(__name__)


def init_aquisition_resource(evtbus, config, primary, secondary):
    resource = AquisitionService(
        evtbus=evtbus,
        config=config,
        primary=primary,
        secondary=secondary,
    )
    try:
        resource.start()
    except Exception as exc:
        logger.critical(f"failed to start acquisition {exc}")
    else:
        yield resource
        resource.stop()
    finally:
        pass


def init_information_resource(evtbus, config):
    resource = InformationService(evtbus=evtbus, config=config)
    resource.start()
    yield resource
    resource.stop()


def init_wled_resource(evtbus, config):
    resource = WledService(evtbus=evtbus, config=config)
    try:
        resource.start()
    except RuntimeError as wledservice_exc:
        # catch exception to make app continue without wled service in case there is a connection problem
        logging.warning(f"WLED module init failed {wledservice_exc}")
        raise wledservice_exc
    else:
        yield resource
        resource.stop()
    finally:
        pass


class ServicesContainer(containers.DeclarativeContainer):
    evtbus = providers.Dependency(instance_of=EventEmitter)
    config = providers.Dependency(instance_of=AppConfig)
    backends = providers.DependenciesContainer()

    # Services: Core
    mediacollection_service = providers.Singleton(
        MediacollectionService, evtbus=evtbus, config=config
    )

    aquisition_service = providers.Resource(
        init_aquisition_resource,
        evtbus=evtbus,
        config=config,
        primary=backends.primary_backend,
        secondary=backends.secondary_backend,
    )

    information_service = providers.Resource(
        init_information_resource, evtbus=evtbus, config=config
    )

    keyboard_service = providers.Factory(KeyboardService, evtbus=evtbus, config=config)

    processing_service = providers.Singleton(
        ProcessingService,
        evtbus=evtbus,
        config=config,
        aquisition_service=aquisition_service,
        mediacollection_service=mediacollection_service,
    )

    system_service = providers.Factory(SystemService, evtbus=evtbus, config=config)

    wled_service = providers.Resource(
        init_wled_resource,
        evtbus=evtbus,
        config=config,
    )
