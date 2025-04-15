import logging
import re
import subprocess
import sys
from pathlib import Path

import serial.tools.list_ports

logger = logging.getLogger(__name__)


def serial_ports() -> list[str]:
    ports = serial.tools.list_ports.comports()
    logger.info(f"found serial ports: {[f'{port.device}: {port.description}' for port in ports]}")
    pyserial_ports = [port.device for port in sorted(ports)]

    # if avail on linux, add also by-id paths to the list for convenience.
    serial_byid_paths = []
    try:
        serial_byid_paths = [str(path) for path in sorted(Path("/dev/serial/by-id/").glob("*"))]
        logger.info(f"found serial by-id ports: {serial_byid_paths}")
    except Exception:
        pass

    return serial_byid_paths + pyserial_ports


def webcameras() -> list[str]:
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

        logger.info(f"found webcameras: {[f'{device}' for device in devices]}")

        return devices

    def _webcameras_darwin() -> list[str]:
        # Returns list of video capture devices using AVFoundation."""
        cmd = ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""]

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # Raise error if ffmpeg fails
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"Failed to list AVFoundation devices: {str(e)}")
            return []

        devices = []
        in_video_section = False

        for line in result.stderr.splitlines():
            # Detect section headers
            if "AVFoundation video devices:" in line:
                in_video_section = True
                continue
            if "AVFoundation audio devices:" in line:
                in_video_section = False
                continue

            # Process video devices
            if in_video_section:
                # Extract device name after index bracket
                if match := re.search(r"\]\s*\[\d+\]\s*(.+)", line):
                    devices.append(match.group(1).strip())

        logger.info(f"Found {len(devices)} AVFoundation video devices: {devices}")
        return devices

    if sys.platform == "win32":
        return _webcameras_windows()
    elif sys.platform == "linux":
        return _webcameras_linux()
    elif sys.platform == "darwin":
        return _webcameras_darwin()
    else:
        raise OSError("platform not supported to enumerate")


def dslr_gphoto2() -> list[int]:
    available_indexes: list[int] = []

    try:
        import gphoto2 as gp  # type: ignore
    except ImportError as exc:
        raise RuntimeError("cannot enumerate gphoto2 cameras because not supported by platform or not installed.") from exc

    camera_list = gp.Camera.autodetect()  # pyright: ignore [reportAttributeAccessIssue]
    if len(camera_list) == 0:
        logger.info("no camera detected")
        return []

    for index, (name, addr) in enumerate(camera_list):
        available_indexes.append(index)
        logger.info(f"found camera - {index}:  {addr}  {name}")

    return available_indexes
