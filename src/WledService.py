# WLED Integration
import json
import time
import serial
from .ConfigSettings import settings
import logging
from pymitter import EventEmitter
logger = logging.getLogger(__name__)

# these presets are set on WLED module to control lights:
PRESET_ID_STANDBY = 1
PRESET_ID_COUNTDOWN = 2
PRESET_ID_SHOOT = 3


class WledService():
    def __init__(self, ee: EventEmitter):
        self._ee = ee
        self._serial = None
        wled_detected = False

        if settings.wled.ENABLED == True:
            if settings.wled.SERIAL_PORT:
                logger.info(
                    f"WledService setup, connecting port {settings.wled.SERIAL_PORT}")
            else:
                logger.error(
                    f"WledService setup abort, invalid serial port {settings.wled.SERIAL_PORT}")
                return
        else:
            logger.info(f"WledService disabled")
            return

        wled_detected = self.initWledDevice()

        if not wled_detected:
            # abort init due to problems
            # program continues this way, but no light integration available, use error log to find out how to solve
            return

        logger.info("register events for WLED")
        self._ee.on("statemachine/armed", self.preset_countdown)
        self._ee.on("frameserver/onCapture", self.preset_shoot)
        self._ee.on("frameserver/onCaptureFinished", self.preset_standby)

        self.preset_standby()

    def initWledDevice(self):
        wled_detected = False

        try:
            self._serial = serial.Serial(
                port=settings.wled.SERIAL_PORT, baudrate=115200, bytesize=8, timeout=1, write_timeout=1, stopbits=serial.STOPBITS_ONE, rtscts=False, dsrdtr=False
            )
        except serial.SerialException as e:
            logger.error(e)
            logger.error(
                "failed to open WLED module, ESP flashed correctly and correct serial port set in config?")

            return wled_detected

        # ask WLED module for version (format: WLED YYYYMMDD)
        self._serial.write(b"v")

        # wait for answer being available
        time.sleep(0.2)

        if self._serial.in_waiting > 0:
            try:
                wled_response = self._serial.readline().decode("ascii").strip()
                # indicates WLED module found:
                wled_detected = "WLED" in wled_response
                logger.info(f"WLED version response: {wled_response}")
            except UnicodeDecodeError as e:
                logger.exception(e)
                logger.error("message from WLED module not understood")

        logger.debug(f"wled_detected={wled_detected}")

        return wled_detected

    def preset_standby(self):
        logger.debug("WledService preset_standby triggered")
        self._write_request(_request_preset(PRESET_ID_STANDBY))

    def preset_countdown(self):
        logger.debug("WledService preset_countdown triggered")
        self._write_request(_request_preset(PRESET_ID_COUNTDOWN))

    def preset_shoot(self):
        logger.debug("WledService preset_shoot triggered")
        self._write_request(_request_preset(PRESET_ID_SHOOT))

    def _write_request(self, request):
        try:
            self._serial.write(request)
        except serial.SerialException as e:
            logger.fatal(
                "error accessing WLED device, connection loss? device unpowered?")
            # TODO: future improvement would be autorecover.


def _request_preset(preset_id: int = -1):
    _request_preset_bytes = json.dumps({'ps': preset_id}).encode()
    logger.debug(f"_request_preset_bytes={_request_preset_bytes}")
    return _request_preset_bytes
