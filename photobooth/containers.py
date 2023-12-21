"""Containers module."""


import logging.config

from dependency_injector import containers, providers

from .appconfig import AppConfig
from .services import loggingservice
from .services.backends.containers import BackendsContainer
from .services.containers import ServicesContainer
from .services.sseservice import SseService

logger = logging.getLogger(f"{__name__}")


class ApplicationContainer(containers.DeclarativeContainer):
    config = providers.Singleton(AppConfig)
    sse_service = providers.Singleton(SseService, config)

    logging_service = providers.Resource(
        loggingservice.LoggingService,
        config=config,
        sse_service=sse_service,
    )

    config_service = providers.Singleton(AppConfig)

    backends = providers.Container(
        BackendsContainer,
        config=config,
    )
    services = providers.Container(
        ServicesContainer,
        config=config,
        backends=backends,
        sse_service=sse_service,
    )
