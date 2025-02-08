import logging

from fastapi import APIRouter

from ...container import container

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/config",
    tags=["config"],
)


@router.get("")
def api_get_config_current_active():
    return container.config_service.get_current(False, "app")  # no secrets, app=AppConfig
