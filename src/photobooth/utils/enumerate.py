import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from threading import Lock

import serial.tools.list_ports
from rclone_api.api import RcloneApi

logger = logging.getLogger(__name__)

enumerate_lock = Lock()  # only one enumeration at the same time to avoid HW access issues


def serial_ports() -> list[str]:
    with enumerate_lock:
        ports = serial.tools.list_ports.comports()
        logger.info(f"found serial ports: {[f'{port.device}: {port.description}' for port in ports]}")
        pyserial_ports = [port.device for port in sorted(ports)]

        # if avail on linux, add also by-id paths to the list for convenience.
        serial_byid_paths = []
        try:
            serial_byid_paths = [str(path) for path in sorted(Path("/dev/serial/by-id/").glob("*"))]
            logger.info(f"found serial by-id ports: {serial_byid_paths}")
        except Exception:
            # if the list cmd errors, we ignore it
            pass

        return serial_byid_paths + pyserial_ports


def webcameras() -> list[str]:
    assert sys.platform in ("win32", "linux", "darwin"), "platform not supported to enumerate"

    def _webcameras_linux() -> list[str]:
        devices: list[str] = []

        try:
            device_paths = Path("/dev/v4l/by-id/").glob("*")
            return [str(path) for path in sorted(device_paths)]

        except Exception as exc:
            logger.warning(f"error enumerating webcams: {exc}")

        logger.info(f"found webcameras: {[f'{device}' for device in devices]}")

        return devices

    def _webcameras_windows() -> list[str]:
        devices: list[str] = []
        try:
            pwsh = r"""
            $cameras = @(Get-PnpDevice -Class "Camera" -Status OK |
                Select-Object -ExpandProperty FriendlyName)

            [pscustomobject]@{
                devices = @($cameras | Sort-Object -Unique)
            } | ConvertTo-Json -Compress
            """

            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", pwsh],
                capture_output=True,
                text=True,
                check=True,
            )
            devices = json.loads(result.stdout)["devices"]

        except Exception as exc:
            logger.warning(f"error enumerating webcams: {exc}")

        logger.info(f"found webcameras: {[f'{device}' for device in devices]}")

        return devices

    def _webcameras_darwin() -> list[str]:
        result = subprocess.run(["system_profiler", "SPCameraDataType"], capture_output=True, text=True)

        # Match lines with exactly 4 spaces, ending with a colon, with no additional colons inside
        camera_names: list[str] = re.findall(r"^\s{4}([^\n:]+):\s*$", result.stdout, re.MULTILINE)
        return [name.strip() for name in camera_names]

    with enumerate_lock:
        if sys.platform == "win32":
            return _webcameras_windows()
        elif sys.platform == "linux":
            return _webcameras_linux()
        elif sys.platform == "darwin":
            return _webcameras_darwin()
        else:
            raise OSError(f"platform {sys.platform} not supported")


def dslr_gphoto2() -> list[int]:
    with enumerate_lock:
        available_indexes: list[int] = []

        import gphoto2 as gp

        camera_list = gp.Camera.autodetect()  # pyright: ignore [reportAttributeAccessIssue]
        if len(camera_list) == 0:
            logger.info("no camera detected")
            return []

        for index, (name, addr) in enumerate(camera_list.items()):
            available_indexes.append(index)
            logger.info(f"found camera - {index}:  {addr}  {name}")

        return available_indexes


def rclone_remotes() -> list[str]:
    with enumerate_lock:
        rclone_api = RcloneApi(bind="localhost:5574", config_file=Path("./config/rclone.conf"))
        rclone_api.start()
        remotes = rclone_api.config_listremotes().remotes
        rclone_api.stop()
        logger.info(f"got remotes: {remotes}")

        return remotes
