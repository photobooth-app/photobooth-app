import logging
from unittest.mock import patch

import pytest

from photobooth.containers import ApplicationContainer
from photobooth.services.config import AppConfig, appconfig
from photobooth.services.containers import ServicesContainer
from photobooth.vendor.packages.keyboard.keyboard import KEY_DOWN
from photobooth.vendor.packages.keyboard.keyboard._keyboard_event import KeyboardEvent

appconfig.__dict__.update(AppConfig())
logger = logging.getLogger(name=None)


@pytest.fixture()
def services() -> ServicesContainer:
    # setup
    application_container = ApplicationContainer()

    services = application_container.services()

    # deliver
    yield services
    services.shutdown_resources()


def test_key_callback_takepic(services: ServicesContainer):
    """try to emulate key presses as best as possible without actual hardware/user input"""

    # modify config
    appconfig.hardwareinputoutput.keyboard_input_enabled = True
    appconfig.hardwareinputoutput.keyboard_input_keycode_takepic = "a"

    keyboard_service = services.keyboard_service()

    if not keyboard_service.is_started():
        logger.info("error setup keyboard service, ignore because it's due to permission on hosted system")
        pytest.skip("system does not allow access to input devices")

    # emulate key presses
    keyboard_service._on_key_callback(KeyboardEvent(event_type=KEY_DOWN, name="a", scan_code=None))


def test_key_callback_takecollage(services: ServicesContainer):
    """try to emulate key presses as best as possible without actual hardware/user input"""

    # modify config
    appconfig.hardwareinputoutput.keyboard_input_enabled = True
    appconfig.hardwareinputoutput.keyboard_input_keycode_takecollage = "c"

    keyboard_service = services.keyboard_service()

    if not keyboard_service.is_started():
        logger.info("error setup keyboard service, ignore because it's due to permission on hosted system")
        pytest.skip("system does not allow access to input devices")

    # emulate key presses
    keyboard_service._on_key_callback(KeyboardEvent(event_type=KEY_DOWN, name="c", scan_code=None))


@patch("subprocess.run")
def test_key_callback_print(mock_run, services: ServicesContainer):
    """try to emulate key presses as best as possible without actual hardware/user input"""

    # modify config
    appconfig.hardwareinputoutput.keyboard_input_enabled = True
    appconfig.hardwareinputoutput.keyboard_input_keycode_print_recent_item = "b"
    appconfig.hardwareinputoutput.printing_enabled = True

    keyboard_service = services.keyboard_service()

    if not keyboard_service.is_started():
        logger.info("error setup keyboard service, ignore because it's due to permission on hosted system")
        pytest.skip("system does not allow access to input devices")

    # emulate key presses
    keyboard_service._on_key_callback(KeyboardEvent(event_type=KEY_DOWN, name="b", scan_code=None))

    # check subprocess.check_call was invoked
    mock_run.assert_called()
