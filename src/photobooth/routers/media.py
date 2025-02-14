import logging
import os
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse
from starlette.staticfiles import NotModifiedResponse, StaticFiles

from ..container import container
from ..database.models import DimensionTypes

logger = logging.getLogger(__name__)
media_router = APIRouter(
    prefix="/media",
    tags=["media"],
)


@media_router.get("/{dimension}/{mediaitem_id}")
def api_getitems(mediaitem_id: UUID, dimension: DimensionTypes, request: Request):
    try:
        headers = {"Cache-Control": "no-cache"}

        item = container.mediacollection_service.get_item(mediaitem_id)
        cacheditem = container.mediacollection_service.cache.get_cached_repr(item, dimension, processed=True)

        # StaticFiles has the check for modification on file basis, we borrow that for now to evaluate if 304 or 200 should be sent.
        # TODO: later we can change the etag calc to something that is avail from the db anyways.
        response = FileResponse(cacheditem.filepath, status_code=status.HTTP_200_OK, headers=headers, stat_result=os.stat(cacheditem.filepath))
        if StaticFiles.is_not_modified(None, response_headers=response.headers, request_headers=request.headers):  # type: ignore
            return NotModifiedResponse(response.headers)
        return response
    except FileNotFoundError as exc:
        logger.warning(f"cannot find mediaitem by id {mediaitem_id}")
        raise HTTPException(status_code=404, detail=f"cannot find mediaitem by id {mediaitem_id}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc
