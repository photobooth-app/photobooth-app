import logging
import keyboard
from src.ConfigSettings import settings

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

    def __init__(self, ee):
        self._ee = ee

        if settings.hardwareinput.ENABLED:
            keyboard.on_press(self.on_key_callback)
        else:
            logger.info(
                "keyboardservice not enabled - enable for keyboard triggers")

    def on_key_callback(self, key):
        logger.debug(f"key '{key.name}' triggered.")

        if key.name == settings.hardwareinput.HW_KEYCODE_TAKEPIC:
            logger.info(
                f"triggered by keyboard input HW_KEYCODE_TAKEPIC={settings.hardwareinput.HW_KEYCODE_TAKEPIC}")
            self._ee.emit("keyboardservice/chose_1pic")
