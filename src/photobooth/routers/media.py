import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..container import container
from ..database.models import DimensionTypes

logger = logging.getLogger(__name__)
media_router = APIRouter(
    prefix="/media",
    tags=["media"],
)


@media_router.get("/{dimension}/{mediaitem_id}")
def api_getitems(mediaitem_id: UUID, dimension: DimensionTypes):
    try:
        # headers = {"Cache-Control": "max-age=86400, must-revalidate"}
        headers = None

        item = container.mediacollection_service.get_item(mediaitem_id)
        cacheditem = container.mediacollection_service.cache.get_cached_repr(item, dimension, processed=True)

        return FileResponse(path=cacheditem.filepath, headers=headers)
    except FileNotFoundError as exc:
        logger.warning(f"cannot find mediaitem by id {mediaitem_id}")
        raise HTTPException(status_code=404, detail=f"cannot find mediaitem by id {mediaitem_id}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc
