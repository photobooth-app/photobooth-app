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
from .config.models.trigger import triggerType
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
    _instances = {}  # Class-level cache for pin instances

    def __new__(cls, pin_number, hold_time=1.0):
        try:
            return cls._instances[pin_number]
        except KeyError:
            _new_instance = super().__new__(cls)
            _new_instance.__init_new__(pin_number, hold_time)
            cls._instances[pin_number] = _new_instance
            return _new_instance

    def __init_new__(self, pin_number, hold_time):
        self.button = Button(pin_number, hold_time=hold_time, bounce_time=DEBOUNCE_TIME)  # type: ignore

        self.callbacks: dict[triggerType, list[tuple[Callable[[int | str], None], tuple, dict[str, Any]]]] = {
            "pressed": [],
            "released": [],
            "longpress": [],
        }

        self.button.when_activated = self._handle_press
        self.button.when_deactivated = self._handle_release
        self.button.when_held = self._handle_hold

    def _handle_event(self, event_type: triggerType):
        for cb, args, kwargs in self.callbacks[event_type]:
            try:
                cb(*args, **kwargs)
            except Exception as exc:
                logger.error(f"error during gpio callback execution: {exc}")
                # no reraise!

    def _handle_press(self):
        self._handle_event("pressed")

    def _handle_release(self):
        self._handle_event("released")

    def _handle_hold(self):
        self._handle_event("longpress")

    def register_callback(self, event_type: triggerType, callback, *args, **kwargs):
        """Register a callback: 'pressed', 'released', or 'longpress'."""

        entry = (callback, args, kwargs)
        if entry not in self.callbacks[event_type]:
            self.callbacks[event_type].append(entry)

    def remove_callback(self, event_type: triggerType, callback):
        """Remove a callback for an event."""
        if callback in self.callbacks[event_type]:
            self.callbacks[event_type] = [(cb, args, kwargs) for cb, args, kwargs in self.callbacks[event_type] if cb != callback]


class GpioService(BaseService):
    def __init__(self, processing_service: ProcessingService, share_service: ShareService, mediacollection_service: MediacollectionService):
        super().__init__()

        self._processing_service = processing_service
        self._share_service = share_service
        self._mediacollection_service = mediacollection_service

    def _handle_action_button(self, action_type: ActionType, action_index: int):
        logger.debug(f"trigger callback for {action_type}:{action_index}")
        self._processing_service.trigger_action(action_type, action_index)

    def _handle_share_button(self, action_index: int):
        logger.debug(f"trigger callback for share:{action_index}")

        mediaitem = self._mediacollection_service.get_item_latest()
        self._share_service.share(mediaitem, action_index)

    def _handle_processing_next_confirm_button(self):
        try:
            self._processing_service.continue_process()
        except Exception as exc:
            # other errors
            logger.critical(exc)

    def _handle_processing_reject_button(self):
        try:
            self._processing_service.reject_capture()
        except Exception as exc:
            # other errors
            logger.critical(exc)

    def _handle_processing_abort_button(self):
        try:
            self._processing_service.abort_process()
        except Exception as exc:
            # other errors
            logger.critical(exc)

    def init_io(self):
        # shutdown
        shutdown_btn = PinHandler(appconfig.hardwareinputoutput.gpio_pin_shutdown, hold_time=HOLD_TIME_SHUTDOWN)
        shutdown_btn.register_callback("longpress", self._shutdown)

        # reboot
        shutdown_btn = PinHandler(appconfig.hardwareinputoutput.gpio_pin_reboot, hold_time=HOLD_TIME_SHUTDOWN)
        shutdown_btn.register_callback("longpress", self._reboot)

        # action buttons dynamic registering
        for action_type in get_args(ActionType):
            for index, config in enumerate(getattr(appconfig.actions, action_type)):
                action_btn = PinHandler(config.trigger.gpio_trigger.pin, hold_time=HOLD_TIME_SHUTDOWN)
                # change press to config.trigger.gpio_trigger.trigger_on
                action_btn.register_callback("pressed", self._handle_action_button, action_type, index)
                print(action_btn)

        # for index, config in enumerate(appconfig.share.actions):
        #     self._setup_share_button(config.trigger.gpio_trigger, index)

    def uninit_io(self):
        return
        if self.shutdown_btn:
            self.shutdown_btn.close()
        if self.reboot_btn:
            self.reboot_btn.close()
        if self.action_btns:
            for btn in self.action_btns:
                btn.close()
        if self.share_btns:
            for btn in self.share_btns:
                btn.close()

    def start(self):
        super().start()

        self.uninit_io()

        self.shutdown_btn = None
        self.reboot_btn = None
        self.action_btns = []
        self.share_btns = []

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

        self.uninit_io()

        super().stopped()

    def _shutdown(self):
        logger.info("trigger _shutdown")
        subprocess.check_call(["poweroff"])

    def _reboot(self):
        logger.info("trigger _reboot")
        subprocess.check_call(["reboot"])
