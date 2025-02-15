import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from ...container import container
from ...database.models import DimensionTypes
from ...services.config.models.models import PilgramFilter, SinglePictureDefinition
from ...services.mediaprocessing.processes import get_filter_preview, process_image_collageimage_animationimage
from ...utils.exceptions import PipelineError
from ...services.config import appconfig

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/mediaprocessing",
    tags=["mediaprocessing"],
)


@router.get("/preview/{mediaitem_id}/{filter}", response_class=Response)
def api_get_preview_image_filtered(mediaitem_id: UUID, filter=None):
    try:
        if appconfig.mediaprocessing.filtertype == "pilgram2":
            item = container.mediacollection_service.get_item(mediaitem_id)
            thumbnail = container.mediacollection_service.cache.get_cached_repr(
                item=item,
                dimension=DimensionTypes.thumbnail,
                processed=False,
            )

            buffer_preview_pipeline_applied = get_filter_preview(thumbnail.filepath, filter)

            return Response(
                content=buffer_preview_pipeline_applied.getvalue(),
                media_type="image/jpeg",
                headers={"Cache-Control": "max-age=3600"},  # cache for 60mins in browser to avoid recomputing every time
            )
        elif appconfig.mediaprocessing.filtertype == "stablediffusion":
            with open("../../../assets/filters/" + filter + ".png") as f:
                content = f.read()
            return Response(
                # @TODO: should add check if the file exists and if the "filter" is in the userselectable filters
                content=content,
                media_type="image/png",
                headers={"Cache-Control": "max-age=3600"},  # cache for 60mins in browser to avoid recomputing every time
            )

    except FileNotFoundError as exc:
        # either db_get_image_by_id or open both raise FileNotFoundErrors if file/db entry not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{mediaitem_id=} cannot be found. {exc}") from exc
    except PipelineError as exc:
        logger.error(f"apply pilgram_stage failed, reason: {exc}.")
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=f"{filter=} cannot be found. {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error creating filtered preview: {exc}") from exc


@router.get("/applyfilter/{mediaitem_id}/{filter}")
def api_get_applyfilter(mediaitem_id: UUID, filter: str | None = None):
    try:
        mediaitem = container.mediacollection_service.get_item(item_id=mediaitem_id)

        # along with mediaitem the config was stored. cast it back to original pydantic type, update filter and forward to processing
        _config = SinglePictureDefinition(**mediaitem.pipeline_config)
        _config.filter = PilgramFilter(filter)  # manually overwrite filter definition
        mediaitem.pipeline_config = _config.model_dump(mode="json")  # if config is updated, it is automatically persisted to disk

        mediaitem_cached_repr_full = container.mediacollection_service.cache.get_cached_repr(
            item=mediaitem,
            dimension=DimensionTypes.full,
            processed=False,
        )

        process_image_collageimage_animationimage(mediaitem_cached_repr_full.filepath, mediaitem)

        # update at last in db after processing is finished because in that moment the clients get their sseUpdate notification and cache is busted
        container.mediacollection_service.update_item(mediaitem)
    except Exception as exc:
        logger.exception(exc)
        logger.error(f"apply pipeline failed, reason: {exc}.")
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=f"apply pipeline failed, reason: {exc}.") from exc
