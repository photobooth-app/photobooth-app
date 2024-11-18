"""
submit events on gpio pin interrups

Pin Numbering: https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering

"""

import subprocess

from gpiozero import Button as ZeroButton

from ..utils.exceptions import ProcessMachineOccupiedError
from .baseservice import BaseService
from .config import appconfig
from .config.groups.actions import GpioTrigger
from .mediacollection.mediaitem import MediaItem
from .mediacollectionservice import MediacollectionService
from .processing.jobmodels import action_type_literal
from .processingservice import ProcessingService
from .shareservice import ShareService
from .sseservice import SseService

HOLD_TIME_SHUTDOWN = 2
HOLD_TIME_REBOOT = 2
DEBOUNCE_TIME = 0.04


class Button(ZeroButton):
    def _fire_held(self):
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
    def __init__(self, action_type: action_type_literal, action_index: int, **kwargs):
        super().__init__(**kwargs)

        self.action_type: action_type_literal = action_type
        self.action_index: int = action_index

    def __repr__(self):
        return f"gpioservice.{self.__class__.__name__} triggers action_type={self.action_type}, action_index={self.action_index} {super().__repr__()}"


class ShareButton(Button):
    def __init__(self, action_index: int, **kwargs):
        super().__init__(**kwargs)

        self.action_index: int = action_index

    def __repr__(self):
        return f"gpioservice.{self.__class__.__name__} triggers share action, action_index={self.action_index} {super().__repr__()}"


class GpioService(BaseService):
    """_summary_"""

    def __init__(
        self,
        sse_service: SseService,
        processing_service: ProcessingService,
        share_service: ShareService,
        mediacollection_service: MediacollectionService,
    ):
        super().__init__(sse_service=sse_service)

        self._processing_service = processing_service
        self._share_service = share_service
        self._mediacollection_service = mediacollection_service

        # input buttons
        self.shutdown_btn: Button = None
        self.reboot_btn: Button = None
        self.action_btns: list[ActionButton] = None
        self.share_btns: list[ShareButton] = None

        # output signals
        # none yet

    def _handle_action_button(self, btn: ActionButton):
        self._logger.debug(f"trigger callback for {btn}")

        # start job

        try:
            self._processing_service.trigger_action(btn.action_type, btn.action_index)
        except ProcessMachineOccupiedError as exc:
            # raised if processingservice not idle
            self._logger.warning(f"only one capture at a time allowed, request ignored: {exc}")
        except Exception as exc:
            # other errors
            self._logger.exception(exc)
            self._logger.critical(exc)

    def _handle_share_button(self, btn: ShareButton):
        self._logger.debug(f"trigger callback for {btn}")

        try:
            mediaitem: MediaItem = self._mediacollection_service.db_get_most_recent_mediaitem()
            self._share_service.share(mediaitem, btn.action_index)
        except BlockingIOError:
            self._logger.warning(f"Wait {self._share_service.remaining_time_blocked():.0f}s until next print is possible.")
        except Exception as exc:
            # other errors
            self._logger.critical(exc)

    def _setup_action_button(self, action_type: action_type_literal, gpio_trigger: GpioTrigger, index: int):
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
            self._logger.warning(f"could not setup action button, error: {exc}")

        else:
            if trigger_on == "pressed":
                btn.when_activated = self._handle_action_button
            elif trigger_on == "longpress":
                btn.when_held = self._handle_action_button
            elif trigger_on == "released":
                btn.when_deactivated = self._handle_action_button

            self.action_btns.append(btn)

            self._logger.debug(f"finished setup: {btn}")

    def _setup_share_button(self, gpio_trigger: GpioTrigger, index: int):
        try:
            pin = gpio_trigger.pin
            trigger_on = gpio_trigger.trigger_on

            if not pin:
                self._logger.info(f"skip register print config {index=} because pin empty")
                return

            btn = ShareButton(
                action_index=index,
                pin=pin,
                hold_time=0.6,
                bounce_time=DEBOUNCE_TIME,
            )

        except Exception as exc:
            self._logger.warning(f"could not setup action button, error: {exc}")

        else:
            if trigger_on == "pressed":
                btn.when_activated = self._handle_share_button
            elif trigger_on == "longpress":
                btn.when_held = self._handle_share_button
            elif trigger_on == "released":
                btn.when_deactivated = self._handle_share_button

            self.share_btns.append(btn)

            self._logger.debug(f"finished setup: {btn}")

    def init_io(self):
        # shutdown
        self.shutdown_btn: Button = Button(
            appconfig.hardwareinputoutput.gpio_pin_shutdown,
            hold_time=HOLD_TIME_SHUTDOWN,
            bounce_time=DEBOUNCE_TIME,
        )
        self.shutdown_btn.when_held = self._shutdown

        # reboot
        self.reboot_btn: Button = Button(
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

    def start(self):
        super().start()

        self.shutdown_btn: Button = None
        self.reboot_btn: Button = None
        self.action_btns: list[ActionButton] = []
        self.share_btns: list[ShareButton] = []

        if not appconfig.hardwareinputoutput.gpio_enabled:
            super().disabled()

        try:
            self.init_io()
        except Exception as exc:
            self._logger.exception(exc)
            self._logger.error(f"init_io failed, GPIO might behave erratic, error: {exc}")

        self._logger.info("gpio enabled - listeners installed")

        super().started()

    def stop(self):
        super().stop()

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

        super().stopped()

    def _shutdown(self):
        self._logger.info("trigger _shutdown")
        subprocess.check_call(["poweroff"])

    def _reboot(self):
        self._logger.info("trigger _reboot")
        subprocess.check_call(["reboot"])
