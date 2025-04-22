"""
submit events on gpio pin interrups

Pin Numbering: https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering

"""

import logging
import subprocess
from collections.abc import Callable
from typing import Any, get_args

from gpiozero import Button as ZeroButton
from gpiozero.exc import BadPinFactory

from ..appconfig import appconfig
from .base import BaseService
from .collection import MediacollectionService
from .config.models.trigger import GpioTrigger, triggerType
from .processing import ActionType, ProcessingService
from .share import ShareService

logger = logging.getLogger(__name__)
HOLD_TIME_SHUTDOWN = 2
HOLD_TIME_REBOOT = 2
DEBOUNCE_TIME = 0.04


class Button(ZeroButton):
    def _fire_held(self):
        assert self.pin_factory
        # workaround for bug in gpiozero https://github.com/gpiozero/gpiozero/issues/697
        # https://github.com/gpiozero/gpiozero/issues/697#issuecomment-1480117579
        # Sometimes the kernel omits edges, so if the last
        # deactivating edge is omitted held keeps firing. So
        # check the current value and send a fake edge to
        # EventsMixin to stop the held events.
        if self.value:
            super()._fire_held()
        else:
            self._fire_events(self.pin_factory.ticks(), False)


class PinHandler:
    _instances: dict[str, "PinHandler"] = {}  # Class-level cache for pin instances

    def __new__(cls, pin_number: str | int, hold_time=1.0):
        if pin_number == "" or None:
            logger.info("Ignored setup gpio-pinhandler because the pin_number given is empty.")
            return
        # ensure it's str always
        pin_number = str(pin_number)  # doesn't harm underlying gpiozero lib but instances[] lookup works

        try:
            return cls._instances[pin_number]
        except KeyError:
            _new_instance = super().__new__(cls)
            _new_instance.__init_new__(pin_number, hold_time)
            cls._instances[pin_number] = _new_instance
            return _new_instance

    def __init_new__(self, pin_number, hold_time):
        self.button = Button(pin_number, hold_time=hold_time, bounce_time=DEBOUNCE_TIME)  # type: ignore

        self.callbacks: dict[triggerType, list[tuple[Callable[..., None], tuple, dict[str, Any]]]] = {
            "pressed": [],
            "released": [],
            "longpress": [],
        }

        self.button.when_activated = self._handle_pressed
        self.button.when_deactivated = self._handle_released
        self.button.when_held = self._handle_longpress

    @classmethod
    def _teardown(cls):
        if not cls._instances:
            return  # nothing to tear down

        logger.info("closing all gpio pin handler instances")
        closed_pins = []
        while cls._instances:
            pin, instance = cls._instances.popitem()
            try:
                instance.button.close()
                del instance
                closed_pins.append(pin)
            except Exception as exc:
                logger.error(f"error closing pin {pin} properly: {exc}")

        cls._instances.clear()

        logger.debug(f"closed gpio pin instances {closed_pins}")

    def _handle_event(self, event_type: triggerType):
        for cb, args, kwargs in self.callbacks[event_type]:
            try:
                cb(*args, **kwargs)
            except Exception as exc:
                logger.error(f"error during gpio callback execution: {exc}")
                # no reraise!

    def _handle_pressed(self):
        self._handle_event("pressed")

    def _handle_released(self):
        self._handle_event("released")

    def _handle_longpress(self):
        self._handle_event("longpress")

    def register_callback(self, event_type: triggerType, callback: Callable[..., None], *args, **kwargs):
        entry = (callback, args, kwargs)
        if entry not in self.callbacks[event_type]:
            # getattr __name__ and fallback if not avail because magic mocks for testing do not have __name__
            logger.info(f"for {self.button.pin} register callback {str(getattr(callback, '__name__', callback))}({args},{kwargs}) ")
            self.callbacks[event_type].append(entry)

    @classmethod
    def pins_assigned(cls):
        return [gpio for gpio in sorted(cls._instances.keys())]


class GpioService(BaseService):
    def __init__(self, processing_service: ProcessingService, share_service: ShareService, mediacollection_service: MediacollectionService):
        super().__init__()

        self._processing_service = processing_service
        self._share_service = share_service
        self._mediacollection_service = mediacollection_service

    def _handle_shutdown(self):
        logger.info("Shutting down host")
        subprocess.check_call(["poweroff"])

    def _handle_reboot(self):
        logger.info("Rebooting host")
        subprocess.check_call(["reboot"])

    def _handle_action_button(self, action_type: ActionType, action_index: int):
        logger.debug(f"trigger callback for {action_type}:{action_index}")

        if not self._processing_service._is_occupied():
            self._processing_service.trigger_action(action_type, action_index)
        else:
            logger.info("ignored gpio action button because there is still a job going on")

    def _handle_share_button(self, action_index: int):
        logger.debug(f"trigger callback for share:{action_index}")

        mediaitem = self._mediacollection_service.get_item_latest()
        self._share_service.share(mediaitem, action_index)

    def _handle_processing_next_confirm_button(self):
        if self._processing_service.is_user_input_requested():
            logger.info("continue process chosen by gpio input")
            self._processing_service.continue_process()

    def _handle_processing_reject_button(self):
        if self._processing_service.is_user_input_requested():
            logger.info("reject process chosen by gpio input")
            self._processing_service.reject_capture()

    def _handle_processing_abort_button(self):
        if self._processing_service.is_user_input_requested():
            logger.info("abort process chosen by gpio input")
            self._processing_service.abort_process()

    def init_io(self):
        shutdown_btn = PinHandler(appconfig.hardwareinputoutput.gpio_pin_shutdown, hold_time=HOLD_TIME_SHUTDOWN)
        if shutdown_btn:
            shutdown_btn.register_callback("longpress", self._handle_shutdown)

        reboot_btn = PinHandler(appconfig.hardwareinputoutput.gpio_pin_reboot, hold_time=HOLD_TIME_SHUTDOWN)
        if reboot_btn:
            reboot_btn.register_callback("longpress", self._handle_reboot)

        for action_type in get_args(ActionType):
            for index, config in enumerate(getattr(appconfig.actions, action_type)):  # here is a typing dissociation, might be addressed later...
                gpio_trigger: GpioTrigger = config.trigger.gpio_trigger

                action_btn = PinHandler(gpio_trigger.pin, hold_time=0.6)
                if action_btn:
                    action_btn.register_callback(gpio_trigger.trigger_on, self._handle_action_button, action_type, index)

        for index, config in enumerate(appconfig.share.actions):
            gpio_trigger: GpioTrigger = config.trigger.gpio_trigger

            share_btn = PinHandler(gpio_trigger.pin, hold_time=0.6)
            if share_btn:
                share_btn.register_callback(gpio_trigger.trigger_on, self._handle_share_button, index)

        job_next_btn = PinHandler(appconfig.hardwareinputoutput.gpio_pin_job_next, hold_time=0.6)
        if job_next_btn:
            job_next_btn.register_callback("pressed", self._handle_processing_next_confirm_button)

        job_reject_btn = PinHandler(appconfig.hardwareinputoutput.gpio_pin_job_reject, hold_time=0.6)
        if job_reject_btn:
            job_reject_btn.register_callback("pressed", self._handle_processing_reject_button)

        job_abort_btn = PinHandler(appconfig.hardwareinputoutput.gpio_pin_job_abort, hold_time=0.6)
        if job_abort_btn:
            job_abort_btn.register_callback("pressed", self._handle_processing_abort_button)

        logger.info(f"Pins assigned to GPIO {PinHandler.pins_assigned()}")

    def start(self):
        super().start()

        if not appconfig.hardwareinputoutput.gpio_enabled:
            super().disabled()
            return

        try:
            self.init_io()
        except BadPinFactory:
            # use separate exception without log actual exception because it looks like everything is breaking apart but only gpio is not supported.
            logger.warning("GPIOzero is enabled but could not find a supported pin factory. Hardware is not supported.")
        except Exception as exc:
            logger.exception(exc)
            logger.error(f"init_io failed, GPIO might behave erratic, error: {exc}")

        logger.info("gpio enabled - listeners installed")

        super().started()

    def stop(self):
        super().stop()

        PinHandler._teardown()

        super().stopped()
