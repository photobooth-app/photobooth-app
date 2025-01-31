"""
_summary_
"""

import logging
import os
import platform
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from .base import BaseService

logger = logging.getLogger(__name__)

# constants
SERVICE_NAME = "photobooth-app"
PIP_PKG_NAME = "photobooth-app"
PHOTOBOOTH_APP_SERVICE_FILE = Path(f"{str(Path.home())}/.local/share/systemd/user/photobooth-app.service")


class SystemService(BaseService):
    """_summary_"""

    def __init__(self):
        super().__init__()

        logger.info("initialized systemservice")

    def start(self):
        super().start()
        pass
        super().started()

    def stop(self):
        super().stop()
        pass
        super().stopped()

    def util_systemd_control(self, state: Literal["start", "stop", "restart"]):
        if not platform.system() == "Linux":
            raise RuntimeError("service control supported on linux platform only")

        try:
            # will return 0 for active else inactive.
            subprocess.run(args=["systemctl", "--user", "is-active", "--quiet", SERVICE_NAME], timeout=10, check=True)
        except subprocess.CalledProcessError as exc:
            # non zero returncode
            logger.warning(f"service {SERVICE_NAME} currently inactive, need to restart by yourself! error {exc}")
        except Exception as exc:
            logger.error(f"error: {exc}")

        else:
            # no error, service restart ok
            logger.info(f"service {SERVICE_NAME} currently active, restarting")
            subprocess.run(["systemctl", "--user", state, SERVICE_NAME])

    def install_service(self):
        # install booth service

        # check for supported platform
        if not platform.system() == "Linux":
            raise RuntimeError("install service not supported on this platform")

        # check if app is installed via pip; if so can install service
        try:
            version(PIP_PKG_NAME)
        except PackageNotFoundError as exc:
            raise RuntimeError("photobooth not installed as pip package, service install only supported for pip installs") from exc

        # install service file and enable
        path_photobooth_service_file = Path(__file__).parent.parent.joinpath("scripts", "systemservice", "photobooth-app.service").resolve()
        path_photobooth_working_dir = Path.cwd().resolve()
        with open(path_photobooth_service_file, encoding="utf-8") as fin:
            PHOTOBOOTH_APP_SERVICE_FILE.parent.mkdir(exist_ok=True, parents=True)
            with open(PHOTOBOOTH_APP_SERVICE_FILE, "w", encoding="utf-8") as fout:
                for line in fin:
                    line_out = line

                    line_out = line_out.replace("##working_dir##", os.path.normpath(path_photobooth_working_dir))
                    line_out = line_out.replace("##sys_executable##", sys.executable)

                    fout.write(line_out)

            logger.info(f"created service file '{PHOTOBOOTH_APP_SERVICE_FILE}'")
            logger.info(f"using working directory '{path_photobooth_working_dir}'")
            logger.info(f"using sys_executable '{sys.executable}'")
        try:
            subprocess.run("systemctl --user enable photobooth-app.service", shell=True)
            logger.info("service enabled")
        except Exception as exc:
            raise RuntimeError("error enable the service") from exc

    def uninstall_service(self):
        # uninstall booth service

        try:
            subprocess.run("systemctl --user disable photobooth-app.service", shell=True)
        except Exception as exc:
            raise RuntimeError("error disable the service") from exc

        try:
            os.remove(PHOTOBOOTH_APP_SERVICE_FILE)
        except Exception as exc:
            raise RuntimeError("could not delete service file") from exc

        logger.info("service disabled and uninstalled service")
