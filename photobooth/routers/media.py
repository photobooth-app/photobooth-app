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
        filepath = container.mediacollection_service.get_mediaitem_file(mediaitem_id, dimension, processed=True)
        return FileResponse(path=filepath)
    except FileNotFoundError as exc:
        logger.warning(f"cannot find mediaitem by id {mediaitem_id}")
        raise HTTPException(status_code=404, detail=f"cannot find mediaitem by id {mediaitem_id}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc
