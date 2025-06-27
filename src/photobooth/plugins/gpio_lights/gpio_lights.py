import logging

from gpiozero import DigitalOutputDevice
from gpiozero.exc import BadPinFactory
from statemachine import Event, State

from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import Events, GpioLightsConfig

logger = logging.getLogger(__name__)


class AppDigitalOutputDevice(DigitalOutputDevice):
    def __init__(self, events: list[Events], *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._events: list[Events] = events


class GpioLights(BasePlugin[GpioLightsConfig]):
    def __init__(self):
        super().__init__()

        self._config: GpioLightsConfig = GpioLightsConfig()
        self._digital_output_devices: list[AppDigitalOutputDevice] = []

    @hookimpl
    def start(self):
        self.uninit_io()

        if not self._config.enabled:
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

        self.light("on@start", True)

    @hookimpl
    def stop(self):
        self.uninit_io()

        logger.info("gpio lights stopped")

    @hookimpl
    def sm_on_enter_state(self, source: State, target: State, event: Event):
        if target.id == "counting":
            self.light("on@countdown_start", True)

        elif target.id == "finished":
            self.light("off@after_finished", False)

    @hookimpl
    def sm_on_exit_state(self, source: State, target: State, event: Event):
        if source.id == "capture":
            self.light("off@after_capture", False)

    def init_io(self):
        for cfg_gpio_light in self._config.gpio_lights:
            self._digital_output_devices.append(
                AppDigitalOutputDevice(
                    cfg_gpio_light.events,
                    pin=cfg_gpio_light.gpio_pin,
                    active_high=cfg_gpio_light.active_high,
                )
            )

    def uninit_io(self):
        while self._digital_output_devices:
            digital_output_device = self._digital_output_devices.pop()
            digital_output_device.off()
            digital_output_device.close()

    def light(self, event: Events, on: bool):
        for device in self._digital_output_devices:
            if event in device._events:
                logger.debug(f"switch gpio_light {device}: {on=}")

                try:
                    device.on() if on else device.off()
                except Exception as exc:
                    logger.error(f"could not switch light, error: {exc}")
