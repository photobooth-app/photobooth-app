""" WLED Integration
"""
import json
import logging
import time
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
        self._serial: serial.Serial = None

    def start(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        if settings.wled.ENABLED is True:
            logger.info(
                f"WledService enabled, trying to setup and connect, {settings.wled.SERIAL_PORT=}"
            )

        else:
            logger.info("WledService disabled")
            return

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
            logger.critical(
                f"failed to open WLED module, ESP flashed and correct serial port set in config? {exc}"
            )

            raise RuntimeError("WLED module connection failed!") from exc

        # ask WLED module for version (format: WLED YYYYMMDD)
        try:
            self._serial.write(b"v")
        except serial.SerialTimeoutException as exc:
            logger.critical(
                f"error sending request to identify WLED module - wrong port? {exc}"
            )
            raise RuntimeError("fail to write identify request to WLED module") from exc

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
            logger.critical(f"message from WLED module not understood {exc}")
        except TimeoutError as exc:
            logger.critical(
                f"WLED device did not respond during setup. Check device and connections! {exc}"
            )

        logger.debug(f"{wled_detected=}")

        if not wled_detected:
            # abort init due to problems
            # program continues this way, but no light integration available,
            # use error log to find out how to solve
            logger.critical(
                "WLED module failed. Please check wiring, device, connection and config."
            )
            raise RuntimeError(
                "WLED module failed. Please check wiring, device, connection and config."
            )

        # we have come this far: wled is properly connected, register listener
        logger.info("register events for WLED")
        self._evtbus.on("statemachine/on_thrill", self.preset_countdown)
        self._evtbus.on("frameserver/onCapture", self.preset_shoot)
        self._evtbus.on("frameserver/onCaptureFinished", self.preset_standby)

        self.preset_standby()

        # add very little time to give wled module and serial connection everything is settled
        time.sleep(0.2)

    def stop(self):
        """close serial port connection"""
        if self._serial:
            logger.info("close port to WLED module")
            self._serial.close()

        time.sleep(0.2)

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
        # _serial is None if not initialized -> return
        # if not open() -> return also, fail in silence
        if not self._serial or not self._serial.is_open:
            logger.warning("WLED module not connected, ignoring request")
            return

        try:
            self._serial.write(request)
        except serial.SerialException as exc:
            logger.fatal(
                f"error accessing WLED device, connection loss? device unpowered? {exc}"
            )
            raise RuntimeError(
                f"error accessing WLED device, connection loss? device unpowered? {exc}"
            ) from exc


def _request_preset(preset_id: int = -1):
    _request_preset_bytes = json.dumps({"ps": preset_id}).encode()
    logger.debug(f"wled request preset id={preset_id}")
    return _request_preset_bytes
