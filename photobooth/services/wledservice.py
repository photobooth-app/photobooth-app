""" WLED Integration
"""
import json
import time

import serial
from pymitter import EventEmitter

from ..appconfig import AppConfig
from .baseservice import BaseService

# these presets are set on WLED module to control lights:
PRESET_ID_STANDBY = 1
PRESET_ID_COUNTDOWN = 2
PRESET_ID_SHOOT = 3


class WledService(BaseService):
    """_summary_"""

    def __init__(self, evtbus: EventEmitter, config: AppConfig):
        super().__init__(evtbus, config=config)

        self._enabled = config.hardwareinputoutput.wled_enabled
        self._serial_port = config.hardwareinputoutput.wled_serial_port

        self._serial: serial.Serial = None

    def start(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        if self._enabled is True:
            self._logger.info(f"WledService enabled, trying to setup and connect, {self._serial_port=}")

        else:
            self._logger.info("WledService disabled")
            return

        try:
            self._serial = serial.Serial(
                port=self._serial_port,
                baudrate=115200,
                bytesize=8,
                timeout=1,
                write_timeout=1,
                stopbits=serial.STOPBITS_ONE,
                rtscts=False,
                dsrdtr=False,
            )

        except serial.SerialException as exc:
            self._logger.critical(f"failed to open WLED module, ESP flashed and correct serial port set in config? {exc}")

            raise RuntimeError("WLED module connection failed!") from exc

        # ask WLED module for version (format: WLED YYYYMMDD)
        try:
            self._serial.write(b"v")
        except serial.SerialTimeoutException as exc:
            self._logger.critical(f"error sending request to identify WLED module - wrong port? {exc}")
            raise RuntimeError("fail to write identify request to WLED module") from exc

        wled_detected = False
        try:
            # readline blocks for timeout seconds (set to 1sec on init), afterwards fails
            wled_response = self._serial.readline()

            if wled_response == b"":
                # timeout is defined by response being empty
                raise TimeoutError("no answer from serial WLED device received within timeout")

            # indicates WLED module found:
            wled_detected = "WLED" in wled_response.decode("ascii").strip()

            self._logger.info(f"WLED version response: {wled_response}")
        except UnicodeDecodeError as exc:
            self._logger.critical(f"message from WLED module not understood {exc}")
        except TimeoutError as exc:
            self._logger.critical(f"WLED device did not respond during setup. Check device and connections! {exc}")

        self._logger.debug(f"{wled_detected=}")

        if not wled_detected:
            # abort init due to problems
            # program continues this way, but no light integration available,
            # use error log to find out how to solve
            self._logger.critical("WLED module failed. Please check wiring, device, connection and config.")
            raise RuntimeError("WLED module failed. Please check wiring, device, connection and config.")

        # we have come this far: wled is properly connected, register listener
        self._logger.info("register events for WLED")
        self._evtbus.on("statemachine/on_thrill", self.preset_thrill)
        self._evtbus.on("frameserver/onCapture", self.preset_shoot)
        self._evtbus.on("frameserver/onCaptureFinished", self.preset_standby)

        self._evtbus.on("wled/preset_standby", self.preset_standby)
        self._evtbus.on("wled/preset_thrill", self.preset_thrill)
        self._evtbus.on("wled/preset_shoot", self.preset_shoot)

        self.preset_standby()

        # add very little time to give wled module and serial connection everything is settled
        time.sleep(0.2)

    def stop(self):
        """close serial port connection"""
        if self._serial:
            self._logger.info("close port to WLED module")
            self._serial.close()

        time.sleep(0.2)

    def preset_standby(self):
        """_summary_"""
        self._logger.info("WledService preset_standby triggered")
        self._write_request(self._request_preset(PRESET_ID_STANDBY))

    def preset_thrill(self):
        """_summary_"""
        self._logger.info("WledService preset_thrill triggered")
        self._write_request(self._request_preset(PRESET_ID_COUNTDOWN))

    def preset_shoot(self):
        """_summary_"""
        self._logger.info("WledService preset_shoot triggered")
        self._write_request(self._request_preset(PRESET_ID_SHOOT))

    def _write_request(self, request):
        # _serial is None if not initialized -> return
        # if not open() -> return also, fail in silence
        if not self._serial or not self._serial.is_open:
            self._logger.warning("WLED module not connected, ignoring request")
            return

        try:
            self._serial.write(request)
        except serial.SerialException as exc:
            self._logger.fatal(f"error accessing WLED device, connection loss? device unpowered? {exc}")
            raise RuntimeError(f"error accessing WLED device, connection loss? device unpowered? {exc}") from exc

    @staticmethod
    def _request_preset(preset_id: int = -1):
        _request_preset_bytes = json.dumps({"ps": preset_id}).encode()
        return _request_preset_bytes
