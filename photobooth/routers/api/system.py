import logging
import os
import signal

from fastapi import APIRouter, HTTPException

from ...container import container

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/system",
    tags=["system"],
)


@router.get("/{action}/{param}")
def api_cmd(
    action,
    param,
):
    logger.info(f"cmd api requested action={action}, param={param}")

    if action == "server" and param == "reboot":
        os.system("reboot")
    elif action == "server" and param == "shutdown":
        os.system("shutdown now")
    elif action == "app" and param == "stop":
        signal.raise_signal(signal.SIGINT)
    elif action == "service" and param == "reload":
        container.stop()
        container.start()
    elif action == "service" and param == "restart":
        container.system_service.util_systemd_control("restart")
    elif action == "service" and param == "stop":
        container.system_service.util_systemd_control("stop")
    elif action == "service" and param == "start":
        container.system_service.util_systemd_control("start")
    elif action == "service" and param == "install":
        try:
            container.system_service.install_service()
        except Exception as exc:
            raise HTTPException(500, f"service install failed: {exc}") from exc
    elif action == "service" and param == "uninstall":
        try:
            container.system_service.uninstall_service()
        except Exception as exc:
            raise HTTPException(500, f"service uninstall failed: {exc}") from exc

    else:
        raise HTTPException(500, f"invalid request action={action}, param={param}")

    return f"action={action}, param={param}"
