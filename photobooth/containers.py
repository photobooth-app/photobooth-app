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
        config=config,
    )

    config_service = providers.Singleton(AppConfig)

    backends = providers.Container(
        BackendsContainer,
        evtbus=evtbus,
        config=config,
    )
    services = providers.Container(
        ServicesContainer,
        evtbus=evtbus,
        config=config,
        backends=backends,
    )
