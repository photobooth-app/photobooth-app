import logging

import pytest
from keyboard import KEY_DOWN, KeyboardEvent
from pymitter import EventEmitter

from photobooth.containers import ApplicationContainer

logger = logging.getLogger(name=None)


def test_key_callback():
    class EventCallbackCalledCheckHelper:
        def __init__(self):
            self.was_called = False

        def callback(self):
            self.was_called = True

    event_chose_1pic_received = EventCallbackCalledCheckHelper()

    ApplicationContainer.config().hardwareinput.keyboard_input_enabled = True
    ApplicationContainer.config().hardwareinput.keyboard_input_keycode_takepic = "a"

    evtbus = EventEmitter()
    try:
        ks = ApplicationContainer.services.keyboard_service(evtbus)
    except Exception as exc:
        logger.info(
            f"error setup keyboard service, ignore because it's due to permission on hosted system, {exc}"
        )
        pytest.skip("system does not allow access to input devices")

    evtbus.on("keyboardservice/chose_1pic", event_chose_1pic_received.callback)

    # emulate key presses
    ks._on_key_callback(KeyboardEvent(event_type=KEY_DOWN, name="a", scan_code=None))

    assert event_chose_1pic_received.was_called is True
