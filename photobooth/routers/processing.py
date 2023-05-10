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
    try:
        processing_service.evt_chose_1pic_get()
        return "OK"
    except RuntimeError as exc:
        # raised if processingservice not idle
        raise HTTPException(
            status_code=400,
            detail=f"only one capture at a time allowed: {exc}",
        ) from exc
    except Exception as exc:
        # other errors
        logger.exception(exc)
        raise HTTPException(
            status_code=500,
            detail=f"something went wrong, Exception: {exc}",
        ) from exc
