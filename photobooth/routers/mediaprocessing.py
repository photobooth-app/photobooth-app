import io
import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Response, status
from PIL import Image

from ..appconfig import EnumPilgramFilter
from ..containers import ApplicationContainer
from ..services.mediacollectionservice import MediacollectionService
from ..services.mediaprocessing.image_pipelinestages import pilgram_stage
from ..utils.exceptions import PipelineError

logger = logging.getLogger(__name__)
mediaprocessing_router = APIRouter(
    prefix="/mediaprocessing",
    tags=["mediaprocessing"],
)


@mediaprocessing_router.get("/list/filter")
@inject
def api_get_list_filteravail(
    mediacollection_service: MediacollectionService = Depends(
        Provide[ApplicationContainer.services.mediacollection_service]
    ),
):
    return [e.value for e in EnumPilgramFilter]


@mediaprocessing_router.get("/preview/{mediaitem_id}/{filter}", response_class=Response)
@inject
def api_get_preview_image_filtered(
    mediaitem_id,
    filter,
    mediacollection_service: MediacollectionService = Depends(
        Provide[ApplicationContainer.services.mediacollection_service]
    ),
):
    try:
        mediaitem = mediacollection_service.db_get_image_by_id(item_id=mediaitem_id)

        with open(mediaitem.path_thumbnail, "rb") as file:
            image_bytes: bytes = file.read()
    except FileNotFoundError as exc:
        # either db_get_image_by_id or open both raise FileNotFoundErrors if file/db entry not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{mediaitem_id=} cannot be found. {exc}",
        ) from exc

    image = Image.open(io.BytesIO(image_bytes))

    try:
        image = pilgram_stage(image, filter)
    except PipelineError as exc:
        logger.error(
            f"apply pilgram_stage failed, reason: {exc}. stage not applied, but continue"
        )
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"{filter=} cannot be found. {exc}",
        ) from exc

    buffer_full_pipeline_applied = io.BytesIO()
    image.save(
        buffer_full_pipeline_applied,
        format="jpeg",
        quality=80,
        optimize=True,
    )
    return Response(
        content=buffer_full_pipeline_applied.getvalue(), media_type="image/jpeg"
    )
