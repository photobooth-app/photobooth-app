import piexif
from pynput import keyboard
import logging
logger = logging.getLogger(__name__)


class KeyboardService():
    """Handles keyboard actions"""

    def __init__(self, cs, ee):
        self._cs = cs
        self._ee = ee

        self._listener = keyboard.Listener(on_release=self.on_release)
        # separate thread
        self._listener.start()

    def on_release(self, key):
        # two types of "keys", Key/KeyCode. KeyCode is normal ASCII Code, Key is special example for arrow up on keyboard.
        # check the keycode with debug log on browser console.
        if isinstance(key, keyboard.Key):
            # special key, identified by terms in this enum: https://github.com/moses-palmer/pynput/blob/078491edf7025033c22a364ee76fb9e79db65fcc/lib/pynput/keyboard/_base.py#L162
            #print('Key:', key.name, key.value.vk)
            name = key.name
        elif isinstance(key, keyboard.KeyCode):
            #print('KeyCode:', key.char, key.vk)
            name = key.char

        logger.debug(f"key named '{name}' triggered.")

        if name == self._cs._current_config["HW_KEYCODE_TAKEPIC"]:
            logger.info("triggered by keyboard input HW_KEYCODE_TAKEPIC")
            self._ee.emit("triggerprocess/chose_1pic")
