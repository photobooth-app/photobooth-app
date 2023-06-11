"""
_summary_
"""
import logging
import os
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pymitter import EventEmitter

from ..appconfig import AppConfig
from .baseservice import BaseService

logger = logging.getLogger(__name__)

# constants
SERVICE_NAME = "photobooth-app"
PIP_PKG_NAME = "photobooth-app"
PHOTOBOOTH_APP_SERVICE_FILE = Path(f"{str(Path.home())}/.local/share/systemd/user/photobooth-app.service")


class SystemService(BaseService):
    """_summary_"""

    def __init__(self, evtbus: EventEmitter, config: AppConfig):
        super().__init__(evtbus, config)

        self._logger.info("initialized systemservice")

    def start(self):
        """_summary_"""

    def stop(self):
        """_summary_"""

    def util_systemd_control(self, state):
        # will return 0 for active else inactive.
        try:
            subprocess.run(
                args=["systemctl", "--user", "is-active", "--quiet", SERVICE_NAME],
                timeout=10,
                check=True,
            )
        except FileNotFoundError:
            self._logger.info(f"command systemctl not found to invoke restart; restart {SERVICE_NAME} by yourself.")
        except subprocess.CalledProcessError as exc:
            # non zero returncode
            self._logger.warning(f"service {SERVICE_NAME} currently inactive, need to restart by yourself! error {exc}")
        except subprocess.TimeoutExpired as exc:
            self._logger.error(f"subprocess timeout {exc}")
        else:
            # no error, service restart ok
            self._logger.info(f"service {SERVICE_NAME} currently active, restarting")
            os.system(f"systemctl --user {state} {SERVICE_NAME}")

    def install_service(self):
        # install booth service

        # check for supported platform
        if not platform.system() == "Linux":
            raise RuntimeError("install service not supported on this platform")

        # check if app is installed via pip; if so can install service
        try:
            version(PIP_PKG_NAME)
        except PackageNotFoundError as exc:
            raise RuntimeError(
                "photobooth not installed as pip package, service install only supported for pip installs"
            ) from exc

        # install service file and enable
        path_photobooth_service_file = (
            Path(__file__).parent.joinpath("assets", "systemservice", "photobooth-app.service").resolve()
        )
        path_photobooth_working_dir = Path.cwd().resolve()
        with open(path_photobooth_service_file, encoding="utf-8") as fin:
            PHOTOBOOTH_APP_SERVICE_FILE.parent.mkdir(exist_ok=True, parents=True)
            logger.info(f"creating service file '{PHOTOBOOTH_APP_SERVICE_FILE}'")
            with open(PHOTOBOOTH_APP_SERVICE_FILE, "w", encoding="utf-8") as fout:
                for line in fin:
                    fout.write(
                        line.replace(
                            "##working_dir##",
                            os.path.normpath(path_photobooth_working_dir),
                        )
                    )
        try:
            subprocess.run("systemctl --user enable photobooth-app.service", shell=True)
        except Exception as exc:
            raise RuntimeError("error enable the service") from exc

        logger.info("service installed and enabled")

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
