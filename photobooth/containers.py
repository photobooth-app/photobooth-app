"""Containers module."""


import logging.config

from dependency_injector import containers, providers

from .services import loggingservice
from .services.backends.containers import BackendsContainer
from .services.config import AppConfig
from .services.containers import ServicesContainer
from .services.sseservice import SseService

logger = logging.getLogger(f"{__name__}")


class ApplicationContainer(containers.DeclarativeContainer):
    sse_service = providers.Singleton(SseService)

    logging_service = providers.Resource(
        loggingservice.LoggingService,
        sse_service=sse_service,
    )

    config_service = providers.Singleton(AppConfig)

    backends = providers.Container(
        BackendsContainer,
    )
    services = providers.Container(
        ServicesContainer,
        backends=backends,
        sse_service=sse_service,
    )
