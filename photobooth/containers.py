"""Containers module."""


import logging.config

from dependency_injector import containers, providers

from .services import loggingservice
from .services.containers import ServicesContainer
from .services.sseservice import SseService

logger = logging.getLogger(f"{__name__}")


class ApplicationContainer(containers.DeclarativeContainer):
    sse_service = providers.Singleton(SseService)

    logging_service = providers.Resource(
        loggingservice.LoggingService,
        sse_service=sse_service,
    )

    services = providers.Container(
        ServicesContainer,
        sse_service=sse_service,
    )
