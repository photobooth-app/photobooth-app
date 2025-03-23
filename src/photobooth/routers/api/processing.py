import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from fastapi.responses import FileResponse

from ...container import container
from ...database.models import DimensionTypes
from ...services.collection import MAP_DIMENSION_TO_PIXEL
from ...utils.resizer import generate_resized

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/processing", tags=["processing"])


@router.get("/approval/{capture_id}", response_class=Response)
def api_get_preview_image_filtered(capture_id: UUID, background_tasks: BackgroundTasks):
    try:
        filepath_in = container.processing_service.get_capture(capture_id).filepath
        filepath_out = Path(NamedTemporaryFile(mode="wb", delete=False, dir="tmp", prefix="approval_img_", suffix=filepath_in.suffix).name)

        generate_resized(filepath_in, filepath_out, MAP_DIMENSION_TO_PIXEL[DimensionTypes.preview])

        background_tasks.add_task(lambda path: path.unlink(), filepath_out)

        return FileResponse(filepath_out)

    except FileNotFoundError as exc:
        # either db_get_image_by_id or open both raise FileNotFoundErrors if file/db entry not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{capture_id=} cannot be found. {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error preview: {exc}") from exc


@router.get("/next")
@router.get("/confirm")
def api_cmd_confirm_get():
    try:
        container.processing_service.continue_process()
        return "OK"
    except Exception as exc:
        # other errors
        logger.critical(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/reject")
def api_cmd_reject_get():
    try:
        container.processing_service.reject_capture()
        return "OK"
    except Exception as exc:
        # other errors
        logger.critical(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/abort")
def api_cmd_abort_get():
    try:
        container.processing_service.abort_process()
        return "OK"
    except Exception as exc:
        # other errors
        logger.critical(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc
