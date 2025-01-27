from gpiozero import DigitalOutputDevice
from gpiozero.exc import BadPinFactory

from .base import BaseService
from .config import appconfig
from .sse import SseService


class GpiooutService(BaseService):
    def __init__(self, sse_service: SseService):
        super().__init__(sse_service=sse_service)

        self.light_out: DigitalOutputDevice = None

    def init_io(self):
        # shutdown
        self.light_out: DigitalOutputDevice = DigitalOutputDevice(appconfig.hardwareinputoutput.gpio_pin_light, active_high=False)

    def uninit_io(self):
        if self.light_out:
            self.light_out.close()

    def start(self):
        super().start()

        self.uninit_io()

        self.light_out: DigitalOutputDevice = None

        if not appconfig.hardwareinputoutput.gpio_enabled:
            super().disabled()
            return

        try:
            self.init_io()
        except BadPinFactory:
            # use separate exception without log actual exception because it looks like everything is breaking apart but only gpio is not supported.
            self._logger.warning("GPIOzero is enabled but could not find a supported pin factory. Hardware is not supported.")
        except Exception as exc:
            self._logger.exception(exc)
            self._logger.error(f"init_io failed, GPIO might behave erratic, error: {exc}")

        self._logger.info("gpio out enabled")

        super().started()

    def stop(self):
        super().stop()

        self.uninit_io()

        super().stopped()

    def light(self, on: bool):
        if self.is_running():
            try:
                self.light_out.on() if on else self.light_out.off()
            except Exception as exc:
                self._logger.error(f"could not switch light, error: {exc}")
