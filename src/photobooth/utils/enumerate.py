import logging

import serial.tools.list_ports

logger = logging.getLogger(__name__)


def serial_ports():
    ports = serial.tools.list_ports.comports()
    logger.info(f"found serial ports: {ports}")

    return [port.name for port in sorted(ports)]
