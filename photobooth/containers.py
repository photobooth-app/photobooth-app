"""Containers module."""


import logging.config

import pymitter
from dependency_injector import containers, providers

from .appconfig import AppConfig
from .services import loggingservice
from .services.backends.containers import BackendsContainer
from .services.containers import ServicesContainer

logger = logging.getLogger(f"{__name__}")


class ApplicationContainer(containers.DeclarativeContainer):
    evtbus = providers.Singleton(pymitter.EventEmitter)
    config = providers.Singleton(AppConfig)

    logging_service = providers.Resource(
        loggingservice.LoggingService,
        evtbus=evtbus,
        debug_level=config().common.DEBUG_LEVEL,
    )

    # TODO: split config (settings and service)
    config_service = providers.Singleton(AppConfig)

    # init loggingservice explicitly at first to ensure it is already instanciated and
    # configured when other services are initialized
    # not working, cause config is not avail yet.
    logging_service.init()

    backends = providers.Container(
        BackendsContainer,
        evtbus=evtbus,
        config=config,
    )
    # for provider in backends.traverse():
    #    logger.info(provider)

    services = providers.Container(
        ServicesContainer, evtbus=evtbus, config=config, backends=backends
    )

    # shutdown before leave and reinit in __main__ again. If in init state, an error is thrown.
    logging_service.shutdown()
