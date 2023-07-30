import logging
from unittest.mock import patch

import pytest
from dependency_injector import providers
from pymitter import EventEmitter

from photobooth.appconfig import AppConfig
from photobooth.services.backends.containers import BackendsContainer
from photobooth.services.containers import ServicesContainer
from photobooth.vendor.packages.keyboard.keyboard import KEY_DOWN
from photobooth.vendor.packages.keyboard.keyboard._keyboard_event import KeyboardEvent

logger = logging.getLogger(name=None)


def test_key_callback_takepic():
    """try to emulate key presses as best as possible without actual hardware/user input"""

    evtbus = providers.Singleton(EventEmitter)
    config = providers.Singleton(AppConfig)
    services = ServicesContainer(
        evtbus=evtbus,
        config=config,
        backends=BackendsContainer(
            evtbus=evtbus,
            config=config,
        ),
    )

    # modify config
    services.config().hardwareinputoutput.keyboard_input_enabled = True
    services.config().hardwareinputoutput.keyboard_input_keycode_takepic = "a"

    services.config().hardwareinputoutput.printing_enabled = True
    services.config().hardwareinputoutput.keyboard_input_keycode_print_recent_item = "b"

    try:
        keyboard_service = services.keyboard_service()
    except Exception as exc:
        logger.info(f"error setup keyboard service, ignore because it's due to permission on hosted system, {exc}")
        pytest.skip("system does not allow access to input devices")

    # emulate key presses
    keyboard_service._on_key_callback(KeyboardEvent(event_type=KEY_DOWN, name="a", scan_code=None))


@patch("subprocess.run")
def test_key_callback_print(mock_run):
    """try to emulate key presses as best as possible without actual hardware/user input"""

    evtbus = providers.Singleton(EventEmitter)
    config = providers.Singleton(AppConfig)
    services = ServicesContainer(
        evtbus=evtbus,
        config=config,
        backends=BackendsContainer(
            evtbus=evtbus,
            config=config,
        ),
    )

    # modify config
    services.config().hardwareinputoutput.keyboard_input_enabled = True
    services.config().hardwareinputoutput.printing_enabled = True
    services.config().hardwareinputoutput.keyboard_input_keycode_print_recent_item = "b"

    try:
        keyboard_service = services.keyboard_service()
    except Exception as exc:
        logger.info(f"error setup keyboard service, ignore because it's due to permission on hosted system, {exc}")
        pytest.skip("system does not allow access to input devices")

    # emulate key presses
    keyboard_service._on_key_callback(KeyboardEvent(event_type=KEY_DOWN, name="b", scan_code=None))

    # check subprocess.check_call was invoked
    mock_run.assert_called()
