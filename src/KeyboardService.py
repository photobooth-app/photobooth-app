import logging
import keyboard
from src.ConfigSettings import settings

logger = logging.getLogger(__name__)


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
            self._ee.emit("triggerprocess/chose_1pic")
