import json
import logging
import threading
import time
from enum import Enum
from queue import Empty, Full, Queue

import serial
from statemachine import Event, State

from ...utils.resilientservice import ResilientService
from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import WledConfig

logger = logging.getLogger(__name__)


# these presets are set on WLED module to control lights:
class WledPreset(Enum):
    STANDBY = 1  # int number is sent to wled module
    THRILL = 2
    SHOOT = 3
    RECORD = 4


class Wled(ResilientService, BasePlugin[WledConfig]):
    def __init__(self):
        super().__init__()

        self._config: WledConfig = WledConfig()

        self._serial: serial.Serial | None = None
        self._service_ready: threading.Event = threading.Event()

        # None in queue can be used on shutdown to reduce waiting for timeout
        # None in variable means there is no wled service running that could process external triggers.
        self._queue: Queue[WledPreset | None] | None = None

    def __str__(self):
        return f"WLED ({self._config.wled_serial_port})"

    @hookimpl
    def start(self):
        """To start the resilient service"""

        if not self._config.wled_enabled:
            logger.info("WledService disabled")
            return

        # check for empty port fails here in start. that means resilientservice is not started
        # and there are no log messages permanently about the false config.
        # but maybe it's better to log this cyclic to show the user there is a mistake in the config?
        if not self._config.wled_serial_port:
            logger.warning("WLED plugin enabled but given serial port is empty. Define a valid port!")
            return

        super().start()

    @hookimpl
    def stop(self):
        """To stop the resilient service"""

        super().stop()

    def setup_resource(self):
        if not self.device_init():
            raise OSError("the wled module could not initialize properly, checks logs and module.")

        # add very little time to give wled module and serial connection everything is settled
        time.sleep(0.2)

        # on run always reset to start with a clear queue
        self._queue = Queue(maxsize=3)

        self.send_preset(WledPreset.STANDBY)

    def teardown_resource(self):
        self._service_ready.clear()

        if self._queue:
            try:
                # send none to stop waiting for any further events and immediate shutdown
                self._queue.put_nowait(None)
            except Exception:
                pass

        if self._serial:
            logger.info("cancel read if any and close port to WLED module")
            self._serial.cancel_read()
            self._serial.close()

    def wait_until_ready(self, timeout: float = 5) -> bool:
        return self._service_ready.wait(timeout=timeout)

    @hookimpl
    def sm_on_enter_state(self, source: State, target: State, event: Event):
        if target.id == "counting":
            self.send_preset(WledPreset.THRILL)

        elif target.id == "finished":
            self.send_preset(WledPreset.STANDBY)

    @hookimpl
    def acq_before_get_still(self):
        self.send_preset(WledPreset.SHOOT)

    @hookimpl
    def acq_before_get_video(self):
        self.send_preset(WledPreset.RECORD)

    @hookimpl
    def acq_after_shot(self):
        self.send_preset(WledPreset.STANDBY)

    def send_preset(self, preset: WledPreset):
        if not self._queue:
            # no queue, request ignored.
            return

        try:
            self._queue.put_nowait(preset)
        except Full:
            logger.warning("the queue to send wled presets is full, maybe the service died?")

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
            raise RuntimeError(f"WLED module connection failed, error {exc}") from exc

        # ask WLED module for version (format: WLED YYYYMMDD)
        try:
            self._serial.write(b"v")
        except serial.SerialTimeoutException as exc:
            logger.critical(f"error sending request to identify WLED module - wrong port? {exc}")
            raise RuntimeError("fail to write identify request to WLED module") from exc

        wled_detected = False

        # readline blocks for timeout seconds (set to 1sec on init), afterwards fails
        wled_response = self._serial.readline(32)
        if wled_response == b"":  # \n is missing, which indicates a timeout
            # timeout is defined by response being empty
            logger.critical("WLED device did not respond during setup. Check device and connections!")
            raise TimeoutError("no answer from serial WLED device received within timeout")

        try:
            # indicates WLED module found:
            wled_detected = "WLED" in wled_response.decode("ascii").strip()
        except UnicodeDecodeError as exc:
            logger.critical(f"message from WLED module not understood {exc} {wled_response}")
            raise RuntimeError("failed to identify WLED device, maybe wrong port chosen?") from exc

        logger.info(f"WLED detected: {'yes' if wled_detected else 'no'}, version response: {wled_response}")

        return wled_detected

    def run_service(self):
        assert self._serial
        assert self._queue

        self._service_ready.set()

        while not self._stop_event.is_set():
            try:
                preset = self._queue.get(timeout=1)
            except Empty:
                continue

            if preset is None:
                # shutdown is requested
                break

            self._serial.write(json.dumps({"ps": preset.value}).encode())

            # add a small delay after every write so wled can settle and on fast changes the LED effect is at least
            # visible for a short time.
            time.sleep(0.25)
