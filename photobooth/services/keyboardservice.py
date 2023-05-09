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


class KeyboardService(BaseService):
    """_summary_"""

    def __init__(self, evtbus: EventEmitter, config: AppConfig):
        super().__init__(evtbus=evtbus, config=config)

        self._config_hardwareinput = config.hardwareinput

        if self._config_hardwareinput.keyboard_input_enabled:
            keyboard.on_press(self._on_key_callback)
        else:
            self._logger.info(
                "keyboardservice not enabled - enable for keyboard triggers"
            )

    def _on_key_callback(self, key):
        """_summary_

        Args:
            key (_type_): _description_
        """
        self._logger.debug(f"key '{key.name}' triggered.")
        self._evtbus.emit(
            "publishSSE",
            sse_event="information",
            sse_data=json.dumps({"lastkeycode": key.name}),
        )

        if key.name == self._config_hardwareinput.keyboard_input_keycode_takepic:
            self._logger.info(
                f"keyboard_input_keycode_takepic="
                f"{self._config_hardwareinput.keyboard_input_keycode_takepic}"
            )
            self._evtbus.emit("keyboardservice/chose_1pic")
