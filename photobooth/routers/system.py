import logging
import os

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException

from ..appconfig import AppConfig
from ..containers import ApplicationContainer
from ..services.systemservice import SystemService

logger = logging.getLogger(__name__)
system_router = APIRouter(
    prefix="/system",
    tags=["system"],
)


@system_router.get("/{action}/{param}")
@inject
def api_cmd(
    action,
    param,
    config_service: AppConfig = Depends(Provide[ApplicationContainer.config_service]),
    system_service: SystemService = Depends(
        Provide[ApplicationContainer.services.system_service]
    ),
):
    logger.info(f"cmd api requested action={action}, param={param}")

    if action == "config" and param == "reset":
        config_service.deleteconfig()
        system_service.util_systemd_control("restart")
    elif action == "config" and param == "restore":
        os.system("reboot")
    elif action == "server" and param == "reboot":
        os.system("reboot")
    elif action == "server" and param == "shutdown":
        os.system("shutdown now")
    elif action == "service" and param == "restart":
        system_service.util_systemd_control("restart")
    elif action == "service" and param == "stop":
        system_service.util_systemd_control("stop")
    elif action == "service" and param == "start":
        system_service.util_systemd_control("start")

    else:
        raise HTTPException(500, f"invalid request action={action}, param={param}")

    return f"action={action}, param={param}"
