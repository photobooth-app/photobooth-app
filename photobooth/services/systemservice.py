"""
_summary_
"""
import logging
import os
import platform
import subprocess
from pathlib import Path

from pymitter import EventEmitter

from ..appconfig import AppConfig
from .baseservice import BaseService

logger = logging.getLogger(__name__)

# constants
SERVICE_NAME = "photobooth-app"


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
        if platform.system() == "Linux":
            path_photobooth_service_file = (
                Path(__file__).parent.joinpath("assets", "systemservice", "photobooth-app.service").resolve()
            )
            path_photobooth_working_dir = Path.cwd().resolve()
            with open(path_photobooth_service_file, encoding="utf-8") as fin:
                compiled_service_file = Path(f"{str(Path.home())}/.local/share/systemd/user/photobooth-app.service")
                compiled_service_file.parent.mkdir(exist_ok=True, parents=True)
                logger.info(f"creating service file '{compiled_service_file}'")
                with open(str(compiled_service_file), "w", encoding="utf-8") as fout:
                    for line in fin:
                        fout.write(
                            line.replace(
                                "##working_dir##",
                                os.path.normpath(path_photobooth_working_dir),
                            )
                        )

            # TODO: _syscall("systemctl --user enable photobooth-app.service")

        else:
            raise RuntimeError("install service not supported on this platform")

    def uninstall_service(self):
        # install booth service
        # TODO: uninstall routing
        pass
