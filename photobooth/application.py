"""Application module."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.staticfiles import StaticFiles

from .__version__ import __version__
from .container import container
from .routers.admin.config import admin_config_router
from .routers.admin.files import admin_files_router
from .routers.aquisition import aquisition_router
from .routers.config import config_router
from .routers.debug import debug_router
from .routers.home import home_router
from .routers.mediacollection import mediacollection_router
from .routers.mediaprocessing import mediaprocessing_router
from .routers.print import print_router
from .routers.processing import processing_router
from .routers.sse import sse_router
from .routers.system import system_router

logger = logging.getLogger(f"{__name__}")

FASTAPI_DECRIPTION = """
Photobooth App 🚀

The photobooth app is written in Python and coming along with a modern Vue frontend.

Following api is provided by the app.

## API may change any time.

"""


def _create_app() -> FastAPI:
    container.logging_service.start()

    _app = FastAPI(
        title="Photobooth App API",
        description=FASTAPI_DECRIPTION,
        version=__version__,
        contact={
            "name": "mgrl",
            "url": "https://github.com/photobooth-app/photobooth-app",
            "email": "me@mgrl.de",
        },
        license_info={
            "name": "MIT",
            "url": "https://github.com/photobooth-app/photobooth-app/blob/main/LICENSE.md",
        },
        docs_url="/api/doc",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        dependencies=[],
    )

    _app.include_router(admin_config_router)
    _app.include_router(admin_files_router)
    _app.include_router(config_router)
    _app.include_router(home_router)
    _app.include_router(aquisition_router)
    _app.include_router(debug_router)
    _app.include_router(mediacollection_router)
    _app.include_router(mediaprocessing_router)
    _app.include_router(print_router)
    _app.include_router(sse_router)
    _app.include_router(system_router)
    _app.include_router(processing_router)
    # serve data directory holding images, thumbnails, ...
    _app.mount("/media", StaticFiles(directory="media"), name="media")
    # if not match anything above, default to deliver static files from web directory
    _app.mount("/", StaticFiles(directory=Path(__file__).parent.resolve().joinpath("web_spa")), name="web_spa")

    async def custom_http_exception_handler(request, exc):
        logger.error(f"HTTPException: {repr(exc)}")
        return await http_exception_handler(request, exc)

    async def validation_exception_handler(request, exc):
        logger.error(f"RequestValidationError: {exc}")
        return await request_validation_exception_handler(request, exc)

    _app.add_exception_handler(HTTPException, custom_http_exception_handler)
    _app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # store container here and wire routers, to inject providers

    return _app


app = _create_app()
