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
from .routers import api, api_admin
from .routers.static import static_router

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
            "name": "mgineer85",
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
    _app.include_router(api.router)
    _app.include_router(api_admin.router)
    _app.include_router(static_router)
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
