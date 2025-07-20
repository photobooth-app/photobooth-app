import logging

from fastapi import APIRouter, HTTPException, status

from ...container import container
from ...services.sse.sse_ import SseEventIntervalInformationRecord, SseEventOnetimeInformationRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/information", tags=["admin", "information"])


@router.get("/cntr/reset/{field}", status_code=status.HTTP_204_NO_CONTENT)  # it's cntr because statscounter is blocked by adblocker often
def api_get_statscounter_reset_field(field: str):
    """ """
    try:
        container.information_service.stats_counter_reset(field)
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"failed to reset stats, error {exc}") from exc


@router.get("/cntr/reset/", status_code=status.HTTP_204_NO_CONTENT)  # it's cntr because statscounter is blocked by adblocker often
def api_get_statscounter_reset_all():
    """ """
    try:
        container.information_service.stats_counter_reset_all()
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"failed to reset stats, error {exc}") from exc


@router.get("/stts/onetime", include_in_schema=True, response_model=SseEventOnetimeInformationRecord)
def api_get_stats_onetime():
    return container.information_service.get_initial_inforecord()


@router.get("/stts/interval", include_in_schema=True, response_model=SseEventIntervalInformationRecord)
def api_get_stats_interval():
    return container.information_service.get_interval_inforecord()
