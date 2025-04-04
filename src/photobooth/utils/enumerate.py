import logging
import subprocess
import sys
from pathlib import Path

import serial.tools.list_ports

logger = logging.getLogger(__name__)


def serial_ports() -> list[str]:
    ports = serial.tools.list_ports.comports()
    logger.info(f"found serial ports: {ports}")

    return [port.name for port in sorted(ports)]


def webcameras() -> list[str]:
    def _webcameras_linux() -> list[str]:
        devices: list[str] = []

        try:
            device_paths = Path("/dev/v4l/by-id/").glob("*")
            return [str(path) for path in sorted(device_paths)]

        except Exception as exc:
            logger.warning(f"error enumerating webcams: {exc}")

        return devices

    def _webcameras_windows() -> list[str]:
        devices = []
        try:
            result = subprocess.run(
                ["powershell", "Get-PnpDevice -Class Camera | Select-Object -ExpandProperty FriendlyName"],
                capture_output=True,
                text=True,
                check=True,
            )

            devices += [line.strip() for line in result.stdout.split("\n") if line.strip()]
        except Exception as exc:
            logger.warning(f"error enumerating webcams: {exc}")

        return devices

    if sys.platform == "win32":
        return _webcameras_windows()
    elif sys.platform == "linux":
        return _webcameras_linux()
    else:
        raise OSError("platform not supported to enumerate")
