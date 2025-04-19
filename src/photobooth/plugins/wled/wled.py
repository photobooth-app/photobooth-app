import json
import logging
import time

import serial
from statemachine import Event, State

from ...utils.repeatedtimer import RepeatedTimer
from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import WledConfig

logger = logging.getLogger(__name__)
# these presets are set on WLED module to control lights:
PRESET_ID_STANDBY = 1
PRESET_ID_COUNTDOWN = 2
PRESET_ID_SHOOT = 3
PRESET_ID_RECORD = 4

RECONNECT_INTERVAL_TIMER = 10


class Wled(BasePlugin[WledConfig]):
    def __init__(self):
        super().__init__()

        self._config: WledConfig = WledConfig()

        self._serial: serial.Serial | None = None
        self._reconnect_interval_timer: RepeatedTimer = RepeatedTimer(RECONNECT_INTERVAL_TIMER, self.connect)

    @hookimpl
    def start(self):
        if not self._config.wled_enabled:
            logger.info("WledService disabled")
            return

        if not self._config.wled_serial_port:
            logger.info("given serial port empty. define valid port!")
            return

        self.connect()

        self._reconnect_interval_timer.start()

        logger.info(f"WledService enabled and initialized, using port {self._config.wled_serial_port}")

    @hookimpl
    def stop(self):
        self._reconnect_interval_timer.stop()

        if self._serial:
            logger.info("close port to WLED module")
            self._serial.close()

    @hookimpl
    def sm_on_enter_state(self, source: State, target: State, event: Event):
        if target.id == "counting":
            self.preset_thrill()

        elif target.id == "record":
            self.preset_record()

        elif target.id == "finished":
            self.preset_standby()

    @hookimpl
    def sm_on_exit_state(self, source: State, target: State, event: Event):
        if source.id == "record":
            self.preset_standby()

    @hookimpl
    def acq_before_shot(self):
        self.preset_shoot()

    @hookimpl
    def acq_after_shot(self):
        self.preset_standby()

    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def connect(self):
        if not self.is_connected():
            try:
                self.device_init()

                # add very little time to give wled module and serial connection everything is settled
                time.sleep(0.2)

                self.preset_standby()
            except Exception as exc:
                logger.warning(f"failed to init WLED! check device, connection and config. {exc}")

    def device_init(self) -> bool:
        try:
            self._serial = serial.Serial(
                port=self._config.wled_serial_port,
                baudrate=115200,
                bytesize=8,
                timeout=1,
                write_timeout=1,
                stopbits=serial.STOPBITS_ONE,
                rtscts=False,
                dsrdtr=False,
            )

        except serial.SerialException as exc:
            logger.critical(f"failed to open WLED module, ESP flashed and correct serial port set in config? {exc}")

            raise RuntimeError("WLED module connection failed!") from exc

        # ask WLED module for version (format: WLED YYYYMMDD)
        try:
            self._serial.write(b"v")
        except serial.SerialTimeoutException as exc:
            logger.critical(f"error sending request to identify WLED module - wrong port? {exc}")
            raise RuntimeError("fail to write identify request to WLED module") from exc

        wled_detected = False
        try:
            # readline blocks for timeout seconds (set to 1sec on init), afterwards fails
            wled_response = self._serial.readline()

            if wled_response == b"":
                # timeout is defined by response being empty
                raise TimeoutError("no answer from serial WLED device received within timeout")

            try:
                # indicates WLED module found:
                wled_detected = "WLED" in wled_response.decode("ascii").strip()
            except UnicodeDecodeError as exc:
                logger.critical(f"message from WLED module not understood {exc} {wled_response}")

        except TimeoutError as exc:
            logger.critical(f"WLED device did not respond during setup. Check device and connections! {exc}")
        else:
            logger.info(f"WLED version response: {wled_response}")
        logger.debug(f"{wled_detected=}")

        if not wled_detected:
            # abort init due to problems
            if self._serial:
                logger.info("close port to WLED module")
                self._serial.close()
            # program continues this way, but no light integration available,
            # use error log to find out how to solve
            logger.critical("WLED module failed. Please check wiring, device, connection and config.")
            raise RuntimeError("WLED module failed. Please check wiring, device, connection and config.")

        return wled_detected

    def preset_standby(self):
        if not self._serial:
            return

        self._write_request(self._request_preset(PRESET_ID_STANDBY))

    def preset_thrill(self):
        if not self._serial:
            return

        self._write_request(self._request_preset(PRESET_ID_COUNTDOWN))

    def preset_shoot(self):
        if not self._serial:
            return

        self._write_request(self._request_preset(PRESET_ID_SHOOT))

    def preset_record(self):
        if not self._serial:
            return

        self._write_request(self._request_preset(PRESET_ID_RECORD))

    def _write_request(self, request: bytes):
        if not self.is_connected():
            logger.warning(f"WLED module not connected, ignoring request '{request}'")
            return

        assert self._serial
        try:
            self._serial.write(request)
        except serial.SerialException as exc:
            # close connection because then the device is unconnected and can be reconnected later.
            self._serial.close()
            logger.warning(f"error accessing WLED device, connection loss? device unpowered? {exc}")

    @staticmethod
    def _request_preset(preset_id: int = -1):
        _request_preset_bytes = json.dumps({"ps": preset_id}).encode()
        return _request_preset_bytes
