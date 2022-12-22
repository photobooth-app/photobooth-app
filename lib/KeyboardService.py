import logging
import keyboard
from lib.ConfigSettings import settings

logger = logging.getLogger(__name__)


class KeyboardService():

    def __init__(self, ee):
        self._ee = ee

        keyboard.on_press(self.on_key_callback)

    def on_key_callback(self, key):
        logger.debug(f"key '{key.name}' triggered.")

        if key.name == settings.common.HW_KEYCODE_TAKEPIC:
            logger.info("triggered by keyboard input HW_KEYCODE_TAKEPIC")
            self._ee.emit("triggerprocess/chose_1pic")
