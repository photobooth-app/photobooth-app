import logging

from gpiozero import DigitalOutputDevice
from gpiozero.exc import BadPinFactory
from statemachine import Event, State

from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import GpioLightsConfig

logger = logging.getLogger(__name__)


class GpioLights(BasePlugin[GpioLightsConfig]):
    def __init__(self):
        super().__init__()

        self._config: GpioLightsConfig = GpioLightsConfig()
        self.light_out: DigitalOutputDevice | None = None

    @hookimpl
    def start(self):
        self.uninit_io()

        if not self._config.plugin_enabled:
            logger.info("gpio lights plugin disabled, start aborted")
            return

        try:
            self.init_io()
        except BadPinFactory:
            # use separate exception without log actual exception because it looks like everything is breaking apart but only gpio is not supported.
            logger.warning("GPIOzero is enabled but could not find a supported pin factory. Hardware is not supported.")
        except Exception as exc:
            logger.exception(exc)
            logger.error(f"init_io failed, GPIO might behave erratic, error: {exc}")

        logger.info("gpio lights enabled and initialized")

    @hookimpl
    def stop(self):
        self.uninit_io()

        logger.info("gpio lights stopped")

    @hookimpl
    def sm_on_enter_state(self, source: State, target: State, event: Event):
        if target.id == "counting":
            self.light(True)

        elif target.id == "finished":
            self.light(False)

    @hookimpl
    def sm_on_exit_state(self, source: State, target: State, event: Event):
        if source.id == "capture":
            if self._config.gpio_light_off_after_capture:
                self.light(False)

        elif source.id == "record":
            self.light(False)

    def init_io(self):
        # shutdown
        self.light_out = DigitalOutputDevice(self._config.gpio_pin_light, active_high=False)

    def uninit_io(self):
        if self.light_out:
            self.light_out.close()
            self.light_out = None

    def light(self, on: bool):
        if self.light_out:
            try:
                self.light_out.on() if on else self.light_out.off()
            except Exception as exc:
                logger.error(f"could not switch light, error: {exc}")
