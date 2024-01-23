import logging

from fastapi import APIRouter, HTTPException

from ..container import container
from ..utils.exceptions import ProcessMachineOccupiedError

logger = logging.getLogger(__name__)
processing_router = APIRouter(
    prefix="/processing",
    tags=["processing"],
)


def _capture(job):
    try:
        job()

        return "OK"
    except ProcessMachineOccupiedError as exc:
        # raised if processingservice not idle
        raise HTTPException(
            status_code=400,
            detail=f"only one capture at a time allowed: {exc}",
        ) from exc
    except Exception as exc:
        # other errors
        logger.exception(exc)
        logger.critical(exc)
        raise HTTPException(
            status_code=500,
            detail=f"something went wrong, Exception: {exc}",
        ) from exc


@processing_router.get("/chose/1pic")
def api_chose_1pic_get():
    return _capture(container.processing_service.start_job_1pic)


@processing_router.get("/chose/collage")
def api_chose_collage_get():
    return _capture(container.processing_service.start_job_collage)


@processing_router.get("/chose/animation")
def api_chose_animation_get():
    return _capture(container.processing_service.start_job_animation)


@processing_router.get("/chose/video")
def api_chose_video_get():
    return _capture(container.processing_service.start_job_video)


@processing_router.get("/cmd/confirm")
def api_cmd_confirm_get():
    try:
        container.processing_service.confirm_capture()
        return "OK"
    except Exception as exc:
        # other errors
        logger.critical(exc)
        raise HTTPException(
            status_code=500,
            detail=f"something went wrong, Exception: {exc}",
        ) from exc


@processing_router.get("/cmd/reject")
def api_cmd_reject_get():
    try:
        container.processing_service.reject_capture()
        return "OK"
    except Exception as exc:
        # other errors
        logger.critical(exc)
        raise HTTPException(
            status_code=500,
            detail=f"something went wrong, Exception: {exc}",
        ) from exc


@processing_router.get("/cmd/abort")
def api_cmd_abort_get():
    try:
        container.processing_service.abort_process()
        return "OK"
    except Exception as exc:
        # other errors
        logger.critical(exc)
        raise HTTPException(
            status_code=500,
            detail=f"something went wrong, Exception: {exc}",
        ) from exc
