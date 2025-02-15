import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
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
        # since we use cache busting now, we can actually use the cache in the browser and do not need revalidation on each display.
        # we need cache busting since there are filter that apply updates to images and the vue rendering is
        # kept-alive so it would not reload images without ? cache busting
        headers = {"Cache-Control": "max-age=86400"}

        item = container.mediacollection_service.get_item(mediaitem_id)
        cacheditem = container.mediacollection_service.cache.get_cached_repr(item, dimension, processed=True)

        return FileResponse(cacheditem.filepath, status_code=status.HTTP_200_OK, headers=headers)

        # alternative option for cache strategy. This would work fine except there is currently
        # no way to make vue rerender existing images in the kept-alive components
        # TODO: keep here for reference some time, but delete soon:
        # headers = {"Cache-Control": "no-cache, must-revalidate"}
        # response = FileResponse(cacheditem.filepath, status_code=status.HTTP_200_OK, headers=headers, stat_result=os.stat(cacheditem.filepath))
        # if StaticFiles.is_not_modified(None, response_headers=response.headers, request_headers=request.headers):  # type: ignore
        #     return NotModifiedResponse(response.headers)
        # return response
    except FileNotFoundError as exc:
        logger.warning(f"cannot find mediaitem by id {mediaitem_id}")
        raise HTTPException(status_code=404, detail=f"cannot find mediaitem by id {mediaitem_id}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc
