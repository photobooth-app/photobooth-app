"""
_summary_
"""
import os
import subprocess

from pymitter import EventEmitter

from .baseservice import BaseService

# constants
SERVICE_NAME = "imageserver"


class SystemService(BaseService):
    """_summary_"""

    def __init__(self, evtbus: EventEmitter):
        super().__init__(evtbus)

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
            self._logger.info(
                f"command systemctl not found to invoke restart; restart {SERVICE_NAME} by yourself."
            )
        except subprocess.CalledProcessError as exc:
            # non zero returncode
            self._logger.warning(
                f"service {SERVICE_NAME} currently inactive, need to restart by yourself! error {exc}"
            )
        except subprocess.TimeoutExpired as exc:
            self._logger.error(f"subprocess timeout {exc}")
        else:
            # no error, service restart ok
            self._logger.info(f"service {SERVICE_NAME} currently active, restarting")
            os.system(f"systemctl --user {state} {SERVICE_NAME}")
