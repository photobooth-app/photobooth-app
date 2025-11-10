import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from ..container import container
from ..database.models import DimensionTypes

logger = logging.getLogger(__name__)
media_router = APIRouter(prefix="/media", tags=["media"])


def _serve_media_item(mediaitem_id: UUID, dimension: DimensionTypes):
    # get/head have same handler but for openapi generation, it needs one method per function call otherwise there are duplicates.

    try:
        # since we use cache busting now, we can actually use the cache in the browser and do not need revalidation on each display.
        # we need cache busting since there are filter that apply updates to images and the vue rendering is
        # kept-alive so it would not reload images without ? cache busting
        headers = {"Cache-Control": "max-age=86400"}

        item = container.mediacollection_service.get_item(mediaitem_id)
        cacheditem = container.mediacollection_service.cache.get_cached_repr(item, dimension, processed=True)

        return FileResponse(cacheditem.filepath, status_code=status.HTTP_200_OK, headers=headers)

    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"cannot find mediaitem by id {mediaitem_id}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc


@media_router.get("/{dimension}/{mediaitem_id}")
def api_getitems_get(mediaitem_id: UUID, dimension: DimensionTypes):
    return _serve_media_item(mediaitem_id, dimension)


@media_router.head("/{dimension}/{mediaitem_id}")
def api_getitems_head(mediaitem_id: UUID, dimension: DimensionTypes):
    """head used for download portal to check if the file is available without downloading it."""
    return _serve_media_item(mediaitem_id, dimension)
