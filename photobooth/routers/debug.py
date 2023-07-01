import logging
import logging.config
from pathlib import Path

from dependency_injector import providers
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.responses import Response

from ..containers import ApplicationContainer
from ..services.baseservice import BaseService

logger = logging.getLogger(__name__)
debug_router = APIRouter(
    prefix="/debug",
    tags=["logs"],
)


@debug_router.get("/log/latest")
async def get_log_latest():
    """provide latest logfile to download
    TODO Handle exception if file not exists

    Returns:
        _type_: _description_
    """

    # might be a bug in fastapi: if file changes after file length determined
    # for header content-length, the browser rejects loading the file.
    # return FileResponse(path="./log/qbooth.log")

    return Response(
        content=Path("./log/qbooth.log").read_text(encoding="utf-8"),
        media_type="text/plain",
    )


@debug_router.get("/service/status")
@inject
async def get_service_status(
    appcontainer: ApplicationContainer = Depends(Provide[ApplicationContainer]),
):
    output_service_status = []
    for provider in appcontainer.traverse(types=[providers.Resource, providers.Singleton, providers.Factory]):
        # print(provider)

        if isinstance(provider(), BaseService):
            service: BaseService = provider()
            # print(f"{type(service).__name__} is a service-type, status: {service.get_status()}")
            output_service_status.append({"service": type(service).__name__, "status": service.get_status().name})

    return output_service_status
