import logging

from fastapi import APIRouter

from ...utils.enumerate import serial_ports, webcameras

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enumerate", tags=["admin", "enumerate"])


@router.get("/serialports")
def api_get_serial_ports():
    return serial_ports()


@router.get("/usbcameras")
def api_get_usbcameras():
    return webcameras()
