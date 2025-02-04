import logging

from fastapi import APIRouter

from ...container import container

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/config",
    tags=["config"],
)


@router.get("/current")
def api_get_config_current_active():
    return container.config_service.get_current(False, None)  # no secrets, None=AppConfig
