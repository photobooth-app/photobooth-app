import logging
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status

from ...container import container

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/mediacollection",
    tags=["mediacollection"],
)


@router.get("/getitems")
def api_getitems() -> list:
    # TODO: improve to deliver a clean MediaItem DTO that can be used by the client automatically typed
    try:
        return container.mediacollection_service.db_get_images_as_dict()
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
def api_gallery_delete(image_id: Annotated[str, Body(embed=True)]) -> None:
    logger.info(f"gallery_delete requested, id={image_id}")
    try:
        container.mediacollection_service.delete_image_by_id(image_id)
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(500, f"deleting failed: {exc}") from exc


@router.get("/delete_all", status_code=status.HTTP_204_NO_CONTENT)
def api_gallery_delete_all() -> None:
    """Warning: deletes all files permanently without any further confirmation

    Raises:
        HTTPException: _description_
    """
    logger.info("delete_all media items requested")
    try:
        container.mediacollection_service.delete_all_mediaitems()
        logger.info("all media successfully deleted")
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(500, f"deleting all media items failed: {exc}") from exc
