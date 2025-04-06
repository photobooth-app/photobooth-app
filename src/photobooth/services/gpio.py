"""
submit events on gpio pin interrups

Pin Numbering: https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering

"""

import logging
import subprocess

from gpiozero import Button as ZeroButton
from gpiozero.exc import BadPinFactory

from ..appconfig import appconfig
from ..utils.exceptions import ProcessMachineOccupiedError
from .base import BaseService
from .collection import MediacollectionService
from .config.groups.actions import GpioTrigger
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


class ActionButton(Button):
    def __init__(self, action_type: ActionType, action_index: int, **kwargs):
        super().__init__(**kwargs)

        self.action_type: ActionType = action_type
        self.action_index: int = action_index

    def __repr__(self):
        return f"gpio.{self.__class__.__name__} triggers action_type={self.action_type}, action_index={self.action_index} {super().__repr__()}"


class ShareButton(Button):
    def __init__(self, action_index: int, **kwargs):
        super().__init__(**kwargs)

        self.action_index: int = action_index

    def __repr__(self):
        return f"gpio.{self.__class__.__name__} triggers share action, action_index={self.action_index} {super().__repr__()}"


class GpioService(BaseService):
    def __init__(self, processing_service: ProcessingService, share_service: ShareService, mediacollection_service: MediacollectionService):
        super().__init__()

        self._processing_service = processing_service
        self._share_service = share_service
        self._mediacollection_service = mediacollection_service

        # input buttons
        self.shutdown_btn: Button | None = None
        self.reboot_btn: Button | None = None
        self.action_btns: list[ActionButton] = []
        self.share_btns: list[ShareButton] = []

        # output signals
        # none yet

    def _handle_action_button(self, btn: ActionButton):
        logger.debug(f"trigger callback for {btn}")

        # start job

        try:
            self._processing_service.trigger_action(btn.action_type, btn.action_index)
        except ProcessMachineOccupiedError as exc:
            # raised if processingservice not idle
            logger.warning(f"only one capture at a time allowed, request ignored: {exc}")
        except Exception as exc:
            # other errors
            logger.exception(exc)
            logger.critical(exc)

    def _handle_share_button(self, btn: ShareButton):
        logger.debug(f"trigger callback for {btn}")

        try:
            mediaitem = self._mediacollection_service.get_item_latest()
            self._share_service.share(mediaitem, btn.action_index)
        except BlockingIOError as exc:
            logger.warning(exc)
        except Exception as exc:
            # other errors
            logger.critical(exc)

    def _setup_action_button(self, action_type: ActionType, gpio_trigger: GpioTrigger, index: int):
        try:
            pin = gpio_trigger.pin
            trigger_on = gpio_trigger.trigger_on

            btn = ActionButton(
                action_type=action_type,
                action_index=index,
                pin=pin,
                hold_time=0.6,
                bounce_time=DEBOUNCE_TIME,
            )

        except Exception as exc:
            logger.warning(f"could not setup action button, error: {exc}")

        else:
            if trigger_on == "pressed":
                btn.when_activated = self._handle_action_button
            elif trigger_on == "longpress":
                btn.when_held = self._handle_action_button
            elif trigger_on == "released":
                btn.when_deactivated = self._handle_action_button

            self.action_btns.append(btn)

            logger.debug(f"finished setup: {btn}")

    def _setup_share_button(self, gpio_trigger: GpioTrigger, index: int):
        try:
            pin = gpio_trigger.pin
            trigger_on = gpio_trigger.trigger_on

            if not pin:
                logger.info(f"skip register print config {index=} because pin empty")
                return

            btn = ShareButton(
                action_index=index,
                pin=pin,
                hold_time=0.6,
                bounce_time=DEBOUNCE_TIME,
            )

        except Exception as exc:
            logger.warning(f"could not setup action button, error: {exc}")

        else:
            if trigger_on == "pressed":
                btn.when_activated = self._handle_share_button
            elif trigger_on == "longpress":
                btn.when_held = self._handle_share_button
            elif trigger_on == "released":
                btn.when_deactivated = self._handle_share_button

            self.share_btns.append(btn)

            logger.debug(f"finished setup: {btn}")

    def init_io(self):
        # shutdown
        self.shutdown_btn = Button(
            appconfig.hardwareinputoutput.gpio_pin_shutdown,
            hold_time=HOLD_TIME_SHUTDOWN,
            bounce_time=DEBOUNCE_TIME,
        )
        self.shutdown_btn.when_held = self._shutdown

        # reboot
        self.reboot_btn = Button(
            appconfig.hardwareinputoutput.gpio_pin_reboot,
            hold_time=HOLD_TIME_REBOOT,
            bounce_time=DEBOUNCE_TIME,
        )
        self.reboot_btn.when_held = self._reboot

        # action buttons dynamic registering
        for index, config in enumerate(appconfig.actions.image):
            self._setup_action_button("image", config.trigger.gpio_trigger, index)
        for index, config in enumerate(appconfig.actions.collage):
            self._setup_action_button("collage", config.trigger.gpio_trigger, index)
        for index, config in enumerate(appconfig.actions.animation):
            self._setup_action_button("animation", config.trigger.gpio_trigger, index)
        for index, config in enumerate(appconfig.actions.video):
            self._setup_action_button("video", config.trigger.gpio_trigger, index)

        for index, config in enumerate(appconfig.share.actions):
            self._setup_share_button(config.trigger.gpio_trigger, index)

    def uninit_io(self):
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
