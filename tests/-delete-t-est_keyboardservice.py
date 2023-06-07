import logging

import pytest
from dependency_injector import providers
from keyboard import KEY_DOWN, KeyboardEvent
from pymitter import EventEmitter

from photobooth.appconfig import AppConfig
from photobooth.services.backends.containers import BackendsContainer
from photobooth.services.containers import ServicesContainer

logger = logging.getLogger(name=None)


def test_key_callback():
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
    services.config().hardwareinput.keyboard_input_enabled = True
    services.config().hardwareinput.keyboard_input_keycode_takepic = "a"

    try:
        keyboard_service = services.keyboard_service()

    except Exception as exc:
        logger.info(f"error setup keyboard service, ignore because it's due to permission on hosted system, {exc}")
        pytest.skip("system does not allow access to input devices")

    # emulate key presses
    keyboard_service._on_key_callback(KeyboardEvent(event_type=KEY_DOWN, name="a", scan_code=None))
