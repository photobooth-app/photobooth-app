"""Application module."""

import logging

from fastapi import FastAPI
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.staticfiles import StaticFiles

# from .routers import home, config, mediacollection
from .containers import ApplicationContainer
from .routers.aquisition import aquisition_router
from .routers.config import config_router
from .routers.home import home_router
from .routers.log import log_router
from .routers.mediacollection import mediacollection_router
from .routers.processing import processing_router
from .routers.sse import sse_router
from .routers.system import system_router

description = """
Photobooth App 🚀

The photobooth app is written in Python and coming along with a modern Vue frontend.

Following api is provided by the app.

## Work in progress, API may change any time.

"""


def _create_app() -> FastAPI:
    application_container = ApplicationContainer()
    logger = logging.getLogger(f"{__name__}")

    app = FastAPI(
        title="Photobooth App API",
        description=description,
        version="0.0.1",
        contact={
            "name": "mgrl",
            "url": "https://github.com/mgrl/photobooth-app",
            "email": "me@mgrl.de",
        },
        license_info={
            "name": "MIT",
            "url": "https://github.com/mgrl/photobooth-app/blob/main/LICENSE.md",
        },
        docs_url="/api/doc",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    app.include_router(config_router)
    app.include_router(home_router)
    app.include_router(aquisition_router)
    app.include_router(log_router)
    app.include_router(mediacollection_router)
    app.include_router(sse_router)
    app.include_router(system_router)
    app.include_router(processing_router)
    # serve data directory holding images, thumbnails, ...
    app.mount("/data", StaticFiles(directory="data"), name="data")
    # if not match anything above, default to deliver static files from web directory
    app.mount("/", StaticFiles(directory="web"), name="web")

    async def custom_http_exception_handler(request, exc):
        logger.error(f"HTTPException: {repr(exc)}")
        return await http_exception_handler(request, exc)

    async def validation_exception_handler(request, exc):
        logger.error(f"RequestValidationError: {exc}")
        return await request_validation_exception_handler(request, exc)

    app.add_exception_handler(HTTPException, custom_http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # store container here and wire routers, to inject providers
    app.container = application_container
    app.container.wire(modules=[__name__], packages=[".routers"])

    return app


app = _create_app()
