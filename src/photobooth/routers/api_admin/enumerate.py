import logging

from fastapi import APIRouter

from ...utils.enumerate import serial_ports

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enumerate", tags=["admin", "enumerate"])


@router.get("/serialports")
def api_get_serialports():
    return serial_ports()
