import logging

from fastapi import APIRouter

from ...services.config import appconfig

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/config",
    tags=["config"],
)


@router.get("/currentActive")
def api_get_config_current_active():
    """returns currently cached and active settings, ui requests this on startup."""
    return appconfig
