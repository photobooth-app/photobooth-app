# Simple test for NeoPixels on Raspberry Pi
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


class WledSerial():
    def __init__(self, ee: EventEmitter):
        self._ee = ee
        self._serial = None
        wled_detected = False

        if settings.wled.ENABLED == True:
            if settings.wled.SERIAL_PORT:
                logger.info(
                    f"WledSerial setup, connecting port {settings.wled.SERIAL_PORT}")
            else:
                logger.error(
                    f"WledSerial setup abort, invalid serial port {settings.wled.SERIAL_PORT}")
                return
        else:
            logger.info(f"WledSerial disabled")
            return

        wled_detected = self.initWledDevice()

        if (wled_detected):
            logger.info("register events for WLED")
            self._ee.on("statemachine/armed", self.startCountdown)
            self._ee.on("frameserver/onCapture", self.captureStart)
            self._ee.on("frameserver/onCaptureFinished", self.captureFinished)

    def initWledDevice(self):
        wled_detected = False

        try:
            self._serial = serial.Serial(
                port=settings.wled.SERIAL_PORT, baudrate=115200, bytesize=8, timeout=2, stopbits=serial.STOPBITS_ONE
            )
        except serial.SerialException as e:
            logger.exception(e)
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

    def startCountdown(self):
        logger.debug("WledSerial startCountdown triggered")
        self._serial.write(_request_preset(PRESET_ID_COUNTDOWN))

    def stopCountdown(self):
        logger.debug("WledSerial startCountdown triggered")
        self._serial.write(_request_preset(PRESET_ID_STANDBY))

    def captureStart(self):
        logger.debug("WledSerial startCountdown triggered")
        self._serial.write(_request_preset(PRESET_ID_SHOOT))

    def captureFinished(self):
        logger.debug("WledSerial startCountdown triggered")
        self._serial.write(_request_preset(PRESET_ID_STANDBY))


def _request_preset(preset_id: int = -1):
    _request_preset_bytes = json.dumps({'ps': preset_id}).encode()
    logger.debug(f"_request_preset_bytes={_request_preset_bytes}")
    return _request_preset_bytes
