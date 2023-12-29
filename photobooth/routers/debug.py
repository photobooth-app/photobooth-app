import logging
import logging.config
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

from ..services.loggingservice import LOG_DIR

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

    log_dir = Path(LOG_DIR)
    list_of_paths = log_dir.glob("*.log")
    latest_path = max(list_of_paths, key=lambda p: p.stat().st_mtime)
    logger.info(f"getting latest logfile: {latest_path}")

    return Response(
        content=latest_path.read_text(encoding="utf-8"),
        media_type="text/plain",
    )


# TODO: not used for now, maybe later...
# @debug_router.get("/service/status")
#
# async def get_service_status(
#     appcontainer: ApplicationContainer = Depends(Provide[ApplicationContainer]),
# ):
#     output_service_status = []
#     for provider in appcontainer.traverse(types=[providers.Resource, providers.Singleton, providers.Factory]):
#         logger.debug(f"checking {provider}")

#         if type(provider) is providers.Resource and not provider.initialized:
#             logger.debug("ignored, resource not initialized.")
#             continue

#         provider_instance = provider()

#         if isinstance(provider_instance, BaseService):
#             service_instance: BaseService = provider_instance
#             logger.debug(f"{type(service_instance).__name__} is a service-type, status: {service_instance.get_status()}")
#             output_service_status.append({"service": type(service_instance).__name__, "status": service_instance.get_status().name})
#         else:
#             logger.debug(f"{provider_instance} ignored")

#     return output_service_status
