"""
submit events on gpio pin interrups

Pin Numbering: https://gpiozero.readthedocs.io/en/stable/recipes.html#pin-numbering

"""

import subprocess

from gpiozero import Button

from ..utils.exceptions import ProcessMachineOccupiedError
from ..utils.helper import is_rpi
from .baseservice import BaseService
from .config import appconfig
from .mediacollection.mediaitem import MediaItem
from .mediacollectionservice import MediacollectionService
from .printingservice import PrintingService
from .processing.jobmodels import action_type_literal
from .processingservice import ProcessingService
from .sseservice import SseService

HOLD_TIME_SHUTDOWN = 2
HOLD_TIME_REBOOT = 2
DEBOUNCE_TIME = None  # due to bugs in GPIOZERO this feature cannot be used and remains to default=None


class ActionButton(Button):
    def __init__(self, action_type: action_type_literal, action_index: int, **kwargs):
        super().__init__(**kwargs)

        self.action_type: action_type_literal = action_type
        self.action_index: int = action_index

    def __repr__(self):
        return f"gpioservice.{self.__class__.__name__} triggers action_type={self.action_type}, action_index={self.action_index} {super().__repr__()}"


class PrintButton(Button):
    def __init__(self, action_index: int, **kwargs):
        super().__init__(**kwargs)

        self.action_index: int = action_index

    def __repr__(self):
        return f"gpioservice.{self.__class__.__name__} triggers printing action, action_index={self.action_index} {super().__repr__()}"


class GpioService(BaseService):
    """_summary_"""

    def __init__(
        self,
        sse_service: SseService,
        processing_service: ProcessingService,
        printing_service: PrintingService,
        mediacollection_service: MediacollectionService,
    ):
        super().__init__(sse_service=sse_service)

        self._processing_service = processing_service
        self._printing_service = printing_service
        self._mediacollection_service = mediacollection_service

        # input buttons
        self.shutdown_btn: Button = None
        self.reboot_btn: Button = None
        self.action_btns: list[ActionButton] = []
        self.print_btns: list[PrintButton] = []
        self.print_recent_item_btn: Button = None

        # output signals
        # none yet

        if appconfig.hardwareinputoutput.gpio_enabled:
            if is_rpi():
                self.init_io()
                self._logger.info("gpio enabled - listeners installed")
            else:
                self._logger.info("platform is not raspberry pi - gpio library is not supported")
        else:
            if is_rpi():
                self._logger.info("gpio not enabled - enable for gpio support on raspberry pi")

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

    def _handle_print_button(self, btn: PrintButton):
        self._logger.debug(f"trigger callback for {btn}")

        try:
            mediaitem: MediaItem = self._mediacollection_service.db_get_most_recent_mediaitem()
            self._printing_service.print(mediaitem, btn.action_index)
        except BlockingIOError:
            self._logger.warning(f"Wait {self._printing_service.remaining_time_blocked():.0f}s until next print is possible.")
        except Exception as exc:
            # other errors
            self._logger.critical(exc)

    def _setup_action_button(self, action_type: action_type_literal, action_config, index: int):
        try:
            pin = action_config.trigger.gpio_trigger_actions.pin
            trigger_on = action_config.trigger.gpio_trigger_actions.trigger_on

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

    def _setup_print_button(self, print_config, index: int):
        try:
            pin = print_config.trigger.gpio_trigger_actions.pin
            trigger_on = print_config.trigger.gpio_trigger_actions.trigger_on

            btn = PrintButton(
                action_index=index,
                pin=pin,
                hold_time=0.6,
                bounce_time=DEBOUNCE_TIME,
            )

        except Exception as exc:
            self._logger.warning(f"could not setup action button, error: {exc}")

        else:
            if trigger_on == "pressed":
                btn.when_activated = self._handle_print_button
            elif trigger_on == "longpress":
                btn.when_held = self._handle_print_button
            elif trigger_on == "released":
                btn.when_deactivated = self._handle_print_button

            self.print_btns.append(btn)

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
            self._setup_action_button("image", config, index)
        for index, config in enumerate(appconfig.actions.collage):
            self._setup_action_button("collage", config, index)
        for index, config in enumerate(appconfig.actions.animation):
            self._setup_action_button("animation", config, index)
        for index, config in enumerate(appconfig.actions.video):
            self._setup_action_button("video", config, index)

        for index, config in enumerate(appconfig.print.print):
            self._setup_print_button(config, index)

    def start(self):
        super().set_status_started()

    def stop(self):
        super().set_status_stopped()

    def _shutdown(self):
        self._logger.info("trigger _shutdown")
        subprocess.check_call(["poweroff"])

    def _reboot(self):
        self._logger.info("trigger _reboot")
        subprocess.check_call(["reboot"])
