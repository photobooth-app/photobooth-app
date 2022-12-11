import logging
import asyncio
from sshkeyboard import listen_keyboard
import threading

#from pynput import keyboard
logger = logging.getLogger(__name__)


class KeyboardService(threading.Thread):

    def __init__(self, cs, ee, name='keyboard-input-thread'):
        self._cs = cs
        self._ee = ee

        self._stop = threading.Event()

        super(KeyboardService, self).__init__(name=name)
        self.start()

    # function using _stop function
    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()

    def run(self):
        while not self.stopped():
            listen_keyboard(
                on_press=self.on_key_callback, until=None, lower=False
            )

    async def on_key_callback(self, key):
        logger.debug(f"key '{key}' triggered.")

        if key == self._cs._current_config["HW_KEYCODE_TAKEPIC"]:
            logger.info("triggered by keyboard input HW_KEYCODE_TAKEPIC")
            self._ee.emit("triggerprocess/chose_1pic")
