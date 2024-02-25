import logging

from fastapi import APIRouter, HTTPException, status

from ...container import container
from ...services.mediacollection.mediaitem import MediaItem

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/print",
    tags=["print"],
)


def _print(mediaitem):
    try:
        container.printing_service.print(mediaitem=mediaitem)
    except BlockingIOError as exc:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail=f"Wait {container.printing_service.remaining_time_blocked():.0f}s until next print is possible.",
        ) from exc
    except ConnectionRefusedError as exc:
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail="Printing is disabled. Configure and enable printing before.",
        ) from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Something went wrong, Exception: {exc}",
        ) from exc


@router.get("/latest")
def api_print_latest():
    latest_mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()
    _print(mediaitem=latest_mediaitem)


@router.get("/item/{id}")
def api_print_item_id(id: str):
    requested_mediaitem: MediaItem = container.mediacollection_service.db_get_image_by_id(id)
    _print(mediaitem=requested_mediaitem)
