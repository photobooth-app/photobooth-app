import logging

from fastapi import APIRouter, status
from fastapi.exceptions import HTTPException

from ...container import container

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/information",
    tags=["admin", "information"],
)


@router.get("/sttscntr/reset/", status_code=status.HTTP_204_NO_CONTENT)  # it's sttscntr because statscounter is blocked by adblocker often
@router.get("/sttscntr/reset/{field}", status_code=status.HTTP_204_NO_CONTENT)  # it's sttscntr because statscounter is blocked by adblocker often
def api_get_statscounter_reset(field: str = ""):
    """ """
    try:
        container.information_service.stats_counter_reset(field)
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"failed to reset stats, error {exc}") from exc
