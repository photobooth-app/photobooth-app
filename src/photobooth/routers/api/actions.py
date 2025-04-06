import logging

from fastapi import APIRouter, HTTPException

from ...container import container
from ...services.processing import ActionType
from ...utils.exceptions import ProcessMachineOccupiedError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("/{action_type}/{index}")
def api_trigger_model(action_type: ActionType, index: int = 0):
    try:
        container.processing_service.trigger_action(action_type, index)

    except ProcessMachineOccupiedError as exc:
        # raised if processingservice not idle
        raise HTTPException(status_code=400, detail=f"only one capture at a time allowed: {exc}") from exc
    except Exception as exc:
        # other errors
        logger.exception(exc)
        logger.critical(exc)
        raise HTTPException(status_code=500, detail=f"something went wrong, Exception: {exc}") from exc
