import logging

from fastapi import APIRouter

from ...container import container
from ...services.config.appconfig_ import AppConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=AppConfig)
def api_get_config_current_active():
    return container.config_service.get_current("app", False)  # no secrets, app=AppConfig
