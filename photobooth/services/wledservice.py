""" WLED Integration
"""
import json
import time

import serial

from ..utils.repeatedtimer import RepeatedTimer
from .baseservice import BaseService
from .config import appconfig
from .sseservice import SseService

# these presets are set on WLED module to control lights:
PRESET_ID_STANDBY = 1
PRESET_ID_COUNTDOWN = 2
PRESET_ID_SHOOT = 3

RECONNECT_INTERVAL_TIMER = 10


class WledService(BaseService):
    """_summary_"""

    def __init__(self, sse_service: SseService):
        super().__init__(sse_service)

        self._enabled = appconfig.hardwareinputoutput.wled_enabled
        self._serial_port = appconfig.hardwareinputoutput.wled_serial_port

        self._serial: serial.Serial = None
        self._reconnect_interval_timer: RepeatedTimer = RepeatedTimer(RECONNECT_INTERVAL_TIMER, self.connect)

    def start(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        if not self._enabled:
            self._logger.info("WledService disabled")
            return

        self.connect()

        self._reconnect_interval_timer.start()

        self._logger.info(f"WledService enabled and initialized, using port {self._serial_port}")

    def stop(self):
        """close serial port connection"""
        self._reconnect_interval_timer.stop()

        if self._serial:
            self._logger.info("close port to WLED module")
            self._serial.close()

    def is_connected(self) -> bool:
        return self._serial and self._serial.is_open

    def connect(self):
        if not self.is_connected():
            try:
                self.device_init()

                # add very little time to give wled module and serial connection everything is settled
                time.sleep(0.2)

                self.preset_standby()
            except Exception as exc:
                self._logger.warning(f"failed to init WLED! check device, connection and config. {exc}")

    def device_init(self) -> bool:
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
            self._logger.critical(f"message from WLED module not understood {exc} {wled_response}")
        except TimeoutError as exc:
            self._logger.critical(f"WLED device did not respond during setup. Check device and connections! {exc}")

        self._logger.debug(f"{wled_detected=}")

        if not wled_detected:
            # abort init due to problems
            if self._serial:
                self._logger.info("close port to WLED module")
                self._serial.close()
            # program continues this way, but no light integration available,
            # use error log to find out how to solve
            self._logger.critical("WLED module failed. Please check wiring, device, connection and config.")
            raise RuntimeError("WLED module failed. Please check wiring, device, connection and config.")

        return wled_detected

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
        if not self.is_connected():
            self._logger.warning("WLED module not connected, ignoring request")
            return

        try:
            self._serial.write(request)
        except serial.SerialException as exc:
            # close connection because then the device is unconnected and can be reconnected later.
            self._serial.close()
            self._logger.warning(f"error accessing WLED device, connection loss? device unpowered? {exc}")

    @staticmethod
    def _request_preset(preset_id: int = -1):
        _request_preset_bytes = json.dumps({"ps": preset_id}).encode()
        return _request_preset_bytes
