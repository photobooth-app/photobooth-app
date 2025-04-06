import io
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from ...container import container
from ...database.models import DimensionTypes
from ...services.config.groups.actions import SingleImageProcessing
from ...services.config.models.models import PluginFilters
from ...services.mediaprocessing.processes import process_image_inner, process_phase1images
from ...services.mediaprocessing.steps.image import get_plugin_userselectable_filters
from ...utils.exceptions import PipelineError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/filter", tags=["filter"])


@router.get("/")
def api_get_userselectable_filters():
    try:
        plugin_results: list[str] = [e[1] for e in get_plugin_userselectable_filters()]

    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error getting selected filters: {exc}") from exc

    return plugin_results


@router.get("/{mediaitem_id}", response_class=Response)
def api_get_preview_image_filtered(mediaitem_id: UUID, filter: str):
    try:
        plugin_filter = PluginFilters(filter)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=f"Filter not available, error: {exc}") from exc

    try:
        mediaitem = container.mediacollection_service.get_item(item_id=mediaitem_id)
        thumbnail = container.mediacollection_service.cache.get_cached_repr(item=mediaitem, dimension=DimensionTypes.thumbnail, processed=False)

        # along with mediaitem the config was stored. cast it back to original pydantic type, update filter and forward to processing
        # all other pipeline-steps need to be disabled here for fast preview. false is default so no need to set here.
        config = SingleImageProcessing(image_filter=plugin_filter)

        manipulated_image = process_image_inner(file_in=thumbnail.filepath, config=config, preview=True)

        buffer_preview_pipeline_applied = io.BytesIO()
        manipulated_image.save(buffer_preview_pipeline_applied, format="jpeg", quality=80, optimize=False)

        return Response(
            content=buffer_preview_pipeline_applied.getvalue(),
            media_type="image/jpeg",
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


@router.patch("/{mediaitem_id}")
def api_applyfilter(mediaitem_id: UUID, filter: str):
    try:
        mediaitem = container.mediacollection_service.get_item(item_id=mediaitem_id)

        # along with mediaitem the config was stored. cast it back to original pydantic type.
        # update filter before validating so if there is a filter applied that is not avail any more,
        # ther eis no validation error and just proceeded with the new filter.
        _config = SingleImageProcessing.model_validate(mediaitem.pipeline_config | {"image_filter": filter})
        mediaitem.pipeline_config = _config.model_dump(mode="json")  # if config is updated, it is automatically persisted to disk

        mediaitem_cached_repr_full = container.mediacollection_service.cache.get_cached_repr(
            item=mediaitem,
            dimension=DimensionTypes.full,
            processed=False,
        )

        process_phase1images(mediaitem_cached_repr_full.filepath, mediaitem)

        # update at last in db after processing is finished because in that moment the clients get their sseUpdate notification and cache is busted
        container.mediacollection_service.update_item(mediaitem)
    except Exception as exc:
        logger.exception(exc)
        logger.error(f"apply pipeline failed, reason: {exc}.")
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=f"apply pipeline failed, reason: {exc}.") from exc
