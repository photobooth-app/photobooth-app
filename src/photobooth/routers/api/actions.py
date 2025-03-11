import logging

from fastapi import APIRouter, HTTPException

from ...container import container
from ...utils.exceptions import ProcessMachineOccupiedError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/actions", tags=["actions"])


def _capture(action_type, action_index: int):
    try:
        container.processing_service.trigger_action(action_type, action_index)

        return "OK"
    except ProcessMachineOccupiedError as exc:
        # raised if processingservice not idle
        raise HTTPException(status_code=400, detail=f"only one capture at a time allowed: {exc}") from exc
    except Exception as exc:
        # other errors
        logger.exception(exc)
        logger.critical(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/image/{index}")
def api_chose_1pic_get(index: int = 0):
    return _capture("image", index)


@router.get("/collage/{index}")
def api_chose_collage_get(index: int = 0):
    return _capture("collage", index)


@router.get("/animation/{index}")
def api_chose_animation_get(index: int = 0):
    return _capture("animation", index)


@router.get("/video/{index}")
def api_chose_video_get(index: int = 0):
    return _capture("video", index)


@router.get("/multicamera/{index}")
def api_chose_multicamera_get(index: int = 0):
    return _capture("multicamera", index)


@router.get("/confirm")
def api_cmd_confirm_get():
    try:
        container.processing_service.confirm_capture()
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


@router.get("/stop")
def api_cmd_stop_get():
    try:
        container.processing_service.stop_recording()
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
