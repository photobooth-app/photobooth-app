""" WLED Integration
"""
import json
import logging
import serial
from pymitter import EventEmitter
from .configsettings import settings

logger = logging.getLogger(__name__)

# these presets are set on WLED module to control lights:
PRESET_ID_STANDBY = 1
PRESET_ID_COUNTDOWN = 2
PRESET_ID_SHOOT = 3


class WledService:
    """_summary_"""

    def __init__(self, evtbus: EventEmitter):
        self._evtbus = evtbus
        self._serial = None
        wled_detected = False

        if settings.wled.ENABLED is True:
            if settings.wled.SERIAL_PORT:
                logger.info(
                    f"WledService setup, connecting port {settings.wled.SERIAL_PORT}"
                )
            else:
                logger.error(
                    f"WledService setup abort, invalid serial port {settings.wled.SERIAL_PORT}"
                )
                return
        else:
            logger.info("WledService disabled")
            return

        wled_detected = self.init_wled_device()

        if not wled_detected:
            # abort init due to problems
            # program continues this way, but no light integration available,
            # use error log to find out how to solve
            return

        logger.info("register events for WLED")
        self._evtbus.on("statemachine/armed", self.preset_countdown)
        self._evtbus.on("httprequest/armed", self.preset_countdown)
        self._evtbus.on("frameserver/onCapture", self.preset_shoot)
        self._evtbus.on("frameserver/onCaptureFinished", self.preset_standby)

        self.preset_standby()

    def init_wled_device(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        wled_detected = False

        try:
            self._serial = serial.Serial(
                port=settings.wled.SERIAL_PORT,
                baudrate=115200,
                bytesize=8,
                timeout=1,
                write_timeout=1,
                stopbits=serial.STOPBITS_ONE,
                rtscts=False,
                dsrdtr=False,
            )
        except serial.SerialException as exc:
            logger.error(exc)
            logger.error(
                "failed to open WLED module, ESP flashed and correct serial port set in config?"
            )

            return wled_detected

        # ask WLED module for version (format: WLED YYYYMMDD)
        try:
            self._serial.write(b"v")
        except serial.SerialTimeoutException as exc:
            logger.error(exc)
            logger.error("error sending request to identify WLED module - wrong port?")
            return wled_detected

        try:
            # readline blocks for timeout seconds (set to 1sec on init), afterwards fails
            wled_response = self._serial.readline()

            if wled_response == b"":
                # timeout is defined by response being empty
                raise TimeoutError(
                    "no answer from serial WLED device received within timeout"
                )

            # indicates WLED module found:
            wled_detected = "WLED" in wled_response.decode("ascii").strip()

            logger.info(f"WLED version response: {wled_response}")
        except UnicodeDecodeError as exc:
            logger.exception(exc)
            logger.error("message from WLED module not understood")
        except TimeoutError as exc:
            logger.exception(exc)
            logger.error(
                "WLED device did not respond during setup. Check device and connections!"
            )

        logger.debug(f"wled_detected={wled_detected}")

        return wled_detected

    def preset_standby(self):
        """_summary_"""
        logger.info("WledService preset_standby triggered")
        self._write_request(_request_preset(PRESET_ID_STANDBY))

    def preset_countdown(self):
        """_summary_"""
        logger.info("WledService preset_countdown triggered")
        self._write_request(_request_preset(PRESET_ID_COUNTDOWN))

    def preset_shoot(self):
        """_summary_"""
        logger.info("WledService preset_shoot triggered")
        self._write_request(_request_preset(PRESET_ID_SHOOT))

    def _write_request(self, request):
        try:
            self._serial.write(request)
        except serial.SerialException as exc:
            logger.fatal(
                f"error accessing WLED device, connection loss? device unpowered? {exc}"
            )


def _request_preset(preset_id: int = -1):
    _request_preset_bytes = json.dumps({"ps": preset_id}).encode()
    logger.debug(f"wled request preset id={preset_id}")
    return _request_preset_bytes
