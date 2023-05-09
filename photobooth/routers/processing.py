import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException

from ..containers import ApplicationContainer
from ..services.processingservice import ProcessingService

logger = logging.getLogger(__name__)
processing_router = APIRouter(
    prefix="/processing",
    tags=["processing"],
)


@processing_router.get("/cmd/capture")
@processing_router.get("/chose/1pic")
@inject
def api_chose_1pic_get(
    processing_service: ProcessingService = Depends(
        Provide[ApplicationContainer.services.processing_service]
    ),
):
    if not processing_service.idle.is_active:
        raise HTTPException(
            status_code=400,
            detail="bad request, only one request at a time!",
        )

    try:
        processing_service.thrill()
        processing_service.countdown()
        processing_service.shoot()
        processing_service.postprocess()
        processing_service.finalize()

        return "OK"
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(
            status_code=500,
            detail=f"something went wrong, Exception: {exc}",
        ) from exc


"""
@ee.on("keyboardservice/chose_1pic")
def evt_chose_1pic_get():
    if not processingpicture.idle.is_active:
        raise RuntimeError("bad request, only one request at a time!")

    processingpicture.thrill()
    processingpicture.countdown()
    processingpicture.shoot()
    processingpicture.postprocess()
    processingpicture.finalize()
    processingpicture.finalize()
"""
