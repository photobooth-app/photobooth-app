import logging
import subprocess
from typing import Literal

from fastapi import APIRouter, HTTPException

from ...appconfig import appconfig
from ...container import container

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["system"])


@router.get("/host/{param}")
def api_cmd_host(param: Literal["reboot", "shutdown"]):
    logger.info(f"api_cmd_host param={param}")

    try:
        if param == "reboot":
            cmd = appconfig.misc.cmd_reboot
        elif param == "shutdown":
            cmd = appconfig.misc.cmd_shutdown

        subprocess.run(args=[cmd], timeout=10, check=True)
    except Exception as exc:
        logger.error(f"could not {param}, error: {exc}")

    return "OK"


@router.get("/service/{param}")
def api_cmd_service(param: Literal["reload"]):
    logger.info(f"api_cmd_service param={param}")

    if param == "reload":
        container.reload()

    return "OK"


@router.get("/systemctl/{param}")
def api_cmd_systemctl(param: Literal["restart", "stop", "start", "install", "uninstall"]):
    logger.info(f"api_cmd_systemctl param={param}")

    if param == "restart":
        container.system_service.util_systemd_control("restart")
    elif param == "stop":
        container.system_service.util_systemd_control("stop")
    elif param == "start":
        container.system_service.util_systemd_control("start")
    elif param == "install":
        try:
            container.system_service.install_service()
        except Exception as exc:
            raise HTTPException(500, f"systemctl install failed: {exc}") from exc
    elif param == "uninstall":
        try:
            container.system_service.uninstall_service()
        except Exception as exc:
            raise HTTPException(500, f"systemctl uninstall failed: {exc}") from exc

    return "OK"
