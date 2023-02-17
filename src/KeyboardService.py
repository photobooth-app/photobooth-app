import logging
import keyboard
from src.ConfigSettings import settings
import json
from pymitter import EventEmitter
logger = logging.getLogger(__name__)

"""
tested following libs:
keyboard: works seamless in win/linux but needs sudo on linux, not maintained actually
pynput: works seamless in win/linux but needs sudo on linux, not working when started as service
pygame: seems to rely on x11/video for input (not avail in service on linux)
hid: untested, needs additional libraries on win/linux to be installed
evdev: linux only
sshkeyboard: ?
"""


class KeyboardService():

    def __init__(self, ee: EventEmitter):
        self._ee: EventEmitter = ee

        if settings.hardwareinput.keyboard_input_enabled:
            keyboard.on_press(self.on_key_callback)
        else:
            logger.info(
                "keyboardservice not enabled - enable for keyboard triggers")

    def on_key_callback(self, key):
        logger.debug(f"key '{key.name}' triggered.")
        self._ee.emit("publishSSE", sse_event="information",
                      sse_data=json.dumps({"lastkeycode": key.name}))

        if key.name == settings.hardwareinput.keyboard_input_keycode_takepic:
            logger.info(
                f"triggered by keyboard input keyboard_input_keycode_takepic={settings.hardwareinput.keyboard_input_keycode_takepic}")
            self._ee.emit("keyboardservice/chose_1pic")
