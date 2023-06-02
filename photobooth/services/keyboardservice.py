# pylint: disable=too-few-public-methods
"""
submit events on keypress to take photos

tested following libs:
keyboard: works seamless in win/linux but needs sudo on linux, not maintained actually
pynput: works seamless in win/linux but needs sudo on linux, not working when started as service
pygame: seems to rely on x11/video for input (not avail in service on linux)
hid: untested, needs additional libraries on win/linux to be installed
evdev: linux only
sshkeyboard: ?
"""
import json

import keyboard
from pymitter import EventEmitter

from ..appconfig import AppConfig
from .baseservice import BaseService
from .processingservice import ProcessingService


class KeyboardService(BaseService):
    """_summary_"""

    def __init__(
        self,
        evtbus: EventEmitter,
        config: AppConfig,
        processing_service: ProcessingService,
    ):
        super().__init__(evtbus=evtbus, config=config)

        self._processing_service = processing_service

        if self._config.hardwareinput.keyboard_input_enabled:
            self._logger.info("keyboardservice enabled - listeners installed")
            keyboard.on_press(self._on_key_callback)
        else:
            self._logger.info("keyboardservice not enabled - enable for keyboard triggers")

    def _on_key_callback(self, key):
        """_summary_

        Args:
            key (_type_): _description_
        """
        self._logger.debug(f"key '{key.name}' triggered.")

        # log to http sse helps finding the right key watching live logs
        self._evtbus.emit(
            "publishSSE",
            sse_event="information",
            sse_data=json.dumps({"lastkeycode": key.name}),
        )

        if key.name == self._config.hardwareinput.keyboard_input_keycode_takepic:
            self._logger.info(f"{self._config.hardwareinput.keyboard_input_keycode_takepic=}")
            self._processing_service.evt_chose_1pic_get()
