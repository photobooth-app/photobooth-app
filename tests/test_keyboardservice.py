import keyboard
from keyboard import KeyboardEvent, KEY_DOWN
from pymitter import EventEmitter
from src.keyboardservice import KeyboardService
from src.configsettings import settings, ConfigSettings
import logging
import time

logger = logging.getLogger(name=None)


def test_key_callback():
    event_chose_1pic_received_confirm = False

    class EventCallbackCalledCheckHelper:
        def __init__(self):
            self.was_called = False

        def callback(self):
            self.was_called = True

    event_chose_1pic_received = EventCallbackCalledCheckHelper()

    settings.hardwareinput.keyboard_input_enabled = True
    settings.hardwareinput.keyboard_input_keycode_takepic = "a"

    evtbus = EventEmitter()
    ks = KeyboardService(evtbus)

    evtbus.on("keyboardservice/chose_1pic", event_chose_1pic_received.callback)

    # emulate key presses
    ks._on_key_callback(KeyboardEvent(event_type=KEY_DOWN, name="a", scan_code=None))

    assert event_chose_1pic_received.was_called == True
