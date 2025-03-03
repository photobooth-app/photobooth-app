"""Application module."""

import logging
import signal
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from types import FrameType

from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles

from .__version__ import __version__
from .container import container
from .routers import api, api_admin
from .routers.media import media_router
from .routers.static import static_router
from .routers.userdata import userdata_router

logger = logging.getLogger(f"{__name__}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # workaround to free resources on shutdown and prevent stalling
    # https://github.com/encode/uvicorn/issues/1579#issuecomment-1419635974

    # start app
    default_sigint_handler = signal.getsignal(signal.SIGINT)

    def terminate_now(signum: int, frame: FrameType | None = None):
        logger.info("shutting down app via signal handler")
        container.stop()
        if callable(default_sigint_handler):
            default_sigint_handler(signum, frame)

    if threading.current_thread() is not threading.main_thread():
        # https://github.com/encode/uvicorn/pull/871
        # Signals can only be listened to from the main thread.
        # usually only during testing, but no need in testing for this.
        logger.info("lifecycle hook not installing signal, because current_thread not main_thread")
    else:
        logger.info("lifecycle hook installing signal to handle app shutdown")
        signal.signal(signal.SIGINT, terminate_now)

    # deliver app
    yield
    # Clean up


def _create_app() -> FastAPI:
    container.logging_service.start()

    _app = FastAPI(
        title="Photobooth-App API",
        description="API may change any time.",
        version=__version__,
        contact={
            "name": "mgineer85",
            "url": "https://github.com/photobooth-app/photobooth-app",
            "email": "me@mgineer85.de",
        },
        license_info={
            "name": "MIT",
            "url": "https://github.com/photobooth-app/photobooth-app/blob/main/LICENSE.md",
        },
        docs_url="/api/doc",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        dependencies=[],
        lifespan=lifespan,
    )
    _app.include_router(api.router)
    _app.include_router(api_admin.router)
    _app.include_router(media_router)
    _app.include_router(static_router)
    _app.include_router(userdata_router)

    # serve the spa
    _app.mount("/", StaticFiles(directory=Path(__file__).parent.resolve().joinpath("web_spa")), name="web_spa")

    async def custom_http_exception_handler(request: Request, exc):
        logger.error(f"HTTPException: {request.url=} {exc=}")
        return await http_exception_handler(request, exc)

    async def validation_exception_handler(request: Request, exc):
        logger.error(f"RequestValidationError: {request.url=} {exc=}")
        return await request_validation_exception_handler(request, exc)

    _app.add_exception_handler(HTTPException, custom_http_exception_handler)
    _app.add_exception_handler(RequestValidationError, validation_exception_handler)

    return _app


app = _create_app()
