import logging

from fastapi import APIRouter, HTTPException, status

from ...container import container
from ...services.mediacollection.mediaitem import MediaItem

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/share",
    tags=["share"],
)


def _share(mediaitem: MediaItem, index: int):
    try:
        container.share_service.share(mediaitem, index)
    except BlockingIOError:
        pass  # informed by sepearate sse event
    except ConnectionRefusedError:
        pass  # informed by sepearate sse event
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Something went wrong, Exception: {exc}",
        ) from exc


@router.get("/actions/{index}")
@router.get("/actions/latest/{index}")
def api_share_latest(index: int = 0):
    try:
        latest_mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {exc}") from exc

    _share(latest_mediaitem, index)


@router.get("/actions/{id}/{index}")
def api_share_item_id(id: str, index: int = 0):
    try:
        requested_mediaitem: MediaItem = container.mediacollection_service.db_get_image_by_id(id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {exc}") from exc
    _share(requested_mediaitem, index)
