import logging
import keyboard

logger = logging.getLogger(__name__)


class KeyboardService():

    def __init__(self, cs, ee):
        self._cs = cs
        self._ee = ee

        keyboard.on_press(self.on_key_callback)

    def on_key_callback(self, key):
        logger.debug(f"key '{key.name}' triggered.")

        if key.name == self._cs._current_config["HW_KEYCODE_TAKEPIC"]:
            logger.info("triggered by keyboard input HW_KEYCODE_TAKEPIC")
            self._ee.emit("triggerprocess/chose_1pic")
