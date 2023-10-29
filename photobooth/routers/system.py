import logging
import os

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException

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
    system_service: SystemService = Depends(Provide[ApplicationContainer.services.system_service]),
    appcontainer: ApplicationContainer = Depends(Provide[ApplicationContainer]),
):
    logger.info(f"cmd api requested action={action}, param={param}")

    if action == "server" and param == "reboot":
        os.system("reboot")
    elif action == "server" and param == "shutdown":
        os.system("shutdown now")
    elif action == "service" and param == "reload":
        appcontainer.shutdown_resources()
        appcontainer.init_resources()
    elif action == "service" and param == "restart":
        system_service.util_systemd_control("restart")
    elif action == "service" and param == "stop":
        system_service.util_systemd_control("stop")
    elif action == "service" and param == "start":
        system_service.util_systemd_control("start")
    elif action == "service" and param == "install":
        try:
            system_service.install_service()
        except Exception as exc:
            raise HTTPException(500, f"service install failed: {exc}") from exc
    elif action == "service" and param == "uninstall":
        try:
            system_service.uninstall_service()
        except Exception as exc:
            raise HTTPException(500, f"service uninstall failed: {exc}") from exc

    else:
        raise HTTPException(500, f"invalid request action={action}, param={param}")

    return f"action={action}, param={param}"
