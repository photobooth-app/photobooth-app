import logging

from fastapi import APIRouter, HTTPException, Response, status

from ...container import container
from ...services.config.models.models import PilgramFilter
from ...utils.exceptions import PipelineError

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/mediaprocessing",
    tags=["mediaprocessing"],
)


@router.get("/preview/{mediaitem_id}/{filter}", response_class=Response)
def api_get_preview_image_filtered(mediaitem_id, filter=None):
    try:
        mediaitem = container.mediacollection_service.db_get_image_by_id(item_id=mediaitem_id)
        buffer_preview_pipeline_applied = container.mediaprocessing_service.get_filter_preview(mediaitem, filter)
        return Response(content=buffer_preview_pipeline_applied.getvalue(), media_type="image/jpeg")

    except FileNotFoundError as exc:
        # either db_get_image_by_id or open both raise FileNotFoundErrors if file/db entry not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{mediaitem_id=} cannot be found. {exc}",
        ) from exc
    except PipelineError as exc:
        logger.error(f"apply pilgram_stage failed, reason: {exc}.")
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"{filter=} cannot be found. {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating filtered preview: {exc}",
        ) from exc


@router.get("/applyfilter/{mediaitem_id}/{filter}")
def api_get_applyfilter(mediaitem_id, filter: str = None):
    try:
        mediaitem = container.mediacollection_service.db_get_image_by_id(item_id=mediaitem_id)

        raise NotImplementedError("error, need to reimplement!")
        # create updated config that is the image is processed according to
        config = container.mediaprocessing_service.get_config_based_on_media_type(mediaitem)
        config.filter = PilgramFilter(filter)  # manually overwrite filter definition

        container.mediaprocessing_service.process_image_collageimage_animationimage(mediaitem, None, config)
    except Exception as exc:
        logger.exception(exc)
        logger.error(f"apply pipeline failed, reason: {exc}.")
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"apply pipeline failed, reason: {exc}.",
        ) from exc
