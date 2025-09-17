import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from ...container import container
from ...database.models import Mediaitem
from ...plugins import pm as pluggy_pm
from ...utils.exceptions import WrongMediaTypeError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/share", tags=["share"])


def _share(mediaitem: Mediaitem, index: int, parameters: dict[str, str] | None):
    try:
        container.share_service.share(mediaitem, index, parameters)
    except (BlockingIOError, ConnectionRefusedError, WrongMediaTypeError):
        pass  # informed by sepearate sse event
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Something went wrong, Exception: {exc}") from exc


@router.post("/actions/{index}")
@router.post("/actions/latest/{index}")
def api_share_latest(index: int = 0, parameters: dict[str, str] | None = None):
    try:
        latest_mediaitem = container.mediacollection_service.get_item_latest()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {exc}") from exc

    _share(latest_mediaitem, index, parameters)


@router.post("/actions/{id}/{index}")
def api_share_item_id(id: UUID, index: int = 0, parameters: dict[str, str] | None = None):
    try:
        requested_mediaitem = container.mediacollection_service.get_item(id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {exc}") from exc
    _share(requested_mediaitem, index, parameters)


@router.get("/download/{id}")
def api_download_item_id_get_sharelinks(id: UUID):  # -> list[str]:
    try:
        requested_mediaitem = container.mediacollection_service.get_item(id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {exc}") from exc

    qrcodeservice_link = container.qr_share_service.get_share_link(identifier=requested_mediaitem.id, filename=requested_mediaitem.processed.name)
    pluggy_links = pluggy_pm.hook.get_share_links(filepath_local=requested_mediaitem.processed)
    pluggy_links_flatten = [x for xs in pluggy_links for x in xs]

    return qrcodeservice_link + pluggy_links_flatten
