import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse

from ...container import container

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/aquisition", tags=["aquisition"])


@router.get("/stream.mjpg")
def video_stream():
    headers = {"Age": "0", "Cache-Control": "no-cache, private", "Pragma": "no-cache"}

    try:
        return StreamingResponse(
            content=container.aquisition_service.gen_stream(),
            headers=headers,
            media_type="multipart/x-mixed-replace; boundary=frame",
        )
    except ConnectionRefusedError as exc:
        logger.warning(exc)
        raise HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED, "preview not enabled") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"preview failed: {exc}") from exc


@router.get("/still")
def api_still_get():
    try:
        file = container.aquisition_service.wait_for_still_file()
        return FileResponse(file, filename=file.name)
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/mode/{mode}", status_code=status.HTTP_202_ACCEPTED)
def api_cmd_aquisition_capturemode_get(mode: Literal["preview", "capture", "video", "idle"] = "preview"):
    """set backends to preview or capture mode (usually automatically switched as needed by processingservice)"""
    if mode == "capture":
        container.aquisition_service.signalbackend_configure_optimized_for_hq_capture()
    elif mode == "preview":
        container.aquisition_service.signalbackend_configure_optimized_for_hq_preview()
    elif mode == "video":
        container.aquisition_service.signalbackend_configure_optimized_for_video()
    elif mode == "idle":
        container.aquisition_service.signalbackend_configure_optimized_for_idle()
