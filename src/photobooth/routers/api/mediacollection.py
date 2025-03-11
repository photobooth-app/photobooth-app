import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from ...container import container
from ...database.schemas import MediaitemPublic

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mediacollection", tags=["mediacollection"])


@router.get("/", response_model=list[MediaitemPublic])
def api_getitems(offset: int = 0, limit: Annotated[int, Query(le=500)] = 500):
    try:
        return container.mediacollection_service.list_items(offset, limit)
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/{item_id}", response_model=MediaitemPublic)
def api_getitem(item_id: UUID):
    try:
        return container.mediacollection_service.get_item(item_id)
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc


@router.delete("/{item_id}")
def api_gallery_delete(item_id: UUID):
    try:
        item = container.mediacollection_service.get_item(item_id, False)
        container.mediacollection_service.delete_item(item)
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(500, f"deleting failed: {exc}") from exc
    return {"ok": True}


@router.delete("/")
def api_gallery_delete_all():
    try:
        container.mediacollection_service.clear_all()
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(500, f"deleting all media items failed: {exc}") from exc

    return {"ok": True}
