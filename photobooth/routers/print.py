import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status

from ..containers import ApplicationContainer
from ..services.mediacollection.mediaitem import MediaItem
from ..services.mediacollectionservice import MediacollectionService
from ..services.printingservice import PrintingService

logger = logging.getLogger(__name__)
print_router = APIRouter(
    prefix="/print",
    tags=["print"],
)


@print_router.get("/latest")
@inject
def api_print_latest(
    ms: MediacollectionService = Depends(Provide[ApplicationContainer.services.mediacollection_service]),
    ps: PrintingService = Depends(Provide[ApplicationContainer.services.printing_service]),
):
    try:
        mediaitem: MediaItem = ms.db_get_most_recent_mediaitem()
        ps.print(mediaitem=mediaitem)
    except BlockingIOError as exc:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail=f"Wait {ps.remaining_time_blocked():.0f}s until next print is possible.",
        ) from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Something went wrong, Exception: {exc}",
        ) from exc


@print_router.get("/item/{id}")
@inject
def api_print_item_id(
    id: str,
    ms: MediacollectionService = Depends(Provide[ApplicationContainer.services.mediacollection_service]),
    ps: PrintingService = Depends(Provide[ApplicationContainer.services.printing_service]),
):
    try:
        mediaitem: MediaItem = ms.db_get_image_by_id(id)
        ps.print(mediaitem=mediaitem)
    except BlockingIOError as exc:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail=f"Wait {ps.remaining_time_blocked():.0f}s until next print is possible.",
        ) from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Something went wrong, Exception: {exc}",
        ) from exc
