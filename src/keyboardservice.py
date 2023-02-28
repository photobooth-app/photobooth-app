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
import logging
import json
import keyboard
from pymitter import EventEmitter
from src.configsettings import settings

logger = logging.getLogger(__name__)


class KeyboardService:
    """_summary_"""

    def __init__(self, evtbus: EventEmitter):
        self._evtbus: EventEmitter = evtbus

        if settings.hardwareinput.keyboard_input_enabled:
            keyboard.on_press(self.on_key_callback)
        else:
            logger.info("keyboardservice not enabled - enable for keyboard triggers")

    def on_key_callback(self, key):
        """_summary_

        Args:
            key (_type_): _description_
        """
        logger.debug(f"key '{key.name}' triggered.")
        self._evtbus.emit(
            "publishSSE",
            sse_event="information",
            sse_data=json.dumps({"lastkeycode": key.name}),
        )

        if key.name == settings.hardwareinput.keyboard_input_keycode_takepic:
            logger.info(
                f"keyboard_input_keycode_takepic="
                f"{settings.hardwareinput.keyboard_input_keycode_takepic}"
            )
            self._evtbus.emit("keyboardservice/chose_1pic")
