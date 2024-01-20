import logging
from unittest.mock import patch

import pytest

from photobooth.container import Container, container
from photobooth.services.config import appconfig
from photobooth.vendor.packages.keyboard.keyboard import KEY_DOWN
from photobooth.vendor.packages.keyboard.keyboard._keyboard_event import KeyboardEvent


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Container:
    # setup
    container.start()

    # deliver
    yield container
    container.stop()


def test_key_callback_takepic(_container: Container):
    """try to emulate key presses as best as possible without actual hardware/user input"""

    # modify config
    appconfig.hardwareinputoutput.keyboard_input_enabled = True
    appconfig.hardwareinputoutput.keyboard_input_keycode_takepic = "a"

    container.stop()
    container.start()

    # emulate key presses
    with patch.object(_container.processing_service, "start_job_1pic"):
        # emulate action
        _container.keyboard_service._on_key_callback(KeyboardEvent(event_type=KEY_DOWN, name="a", scan_code=None))
        _container.processing_service.start_job_1pic.assert_called()


def test_key_callback_takecollage(_container: Container):
    """try to emulate key presses as best as possible without actual hardware/user input"""

    # modify config
    appconfig.hardwareinputoutput.keyboard_input_enabled = True
    appconfig.hardwareinputoutput.keyboard_input_keycode_takecollage = "c"

    container.stop()
    container.start()

    # emulate key presses
    with patch.object(_container.processing_service, "start_job_collage"):
        # emulate action
        _container.keyboard_service._on_key_callback(KeyboardEvent(event_type=KEY_DOWN, name="c", scan_code=None))
        _container.processing_service.start_job_collage.assert_called()


def test_key_callback_takeanimation(_container: Container):
    """try to emulate key presses as best as possible without actual hardware/user input"""

    # modify config
    appconfig.hardwareinputoutput.keyboard_input_enabled = True
    appconfig.hardwareinputoutput.keyboard_input_keycode_takeanimation = "g"

    container.stop()
    container.start()

    if not _container.keyboard_service.is_started():
        logger.info("error setup keyboard service, ignore because it's due to permission on hosted system")
        pytest.skip("system does not allow access to input devices")

    # emulate key presses
    with patch.object(_container.processing_service, "start_job_animation"):
        # emulate action
        _container.keyboard_service._on_key_callback(KeyboardEvent(event_type=KEY_DOWN, name="g", scan_code=None))
        _container.processing_service.start_job_animation.assert_called()


@patch("subprocess.run")
def test_key_callback_print(mock_run, _container: Container):
    """try to emulate key presses as best as possible without actual hardware/user input"""

    # modify config
    appconfig.hardwareinputoutput.keyboard_input_enabled = True
    appconfig.hardwareinputoutput.keyboard_input_keycode_print_recent_item = "b"
    appconfig.hardwareinputoutput.printing_enabled = True

    container.stop()
    container.start()

    container.processing_service.start_job_1pic()

    if not _container.keyboard_service.is_started():
        logger.info("error setup keyboard service, ignore because it's due to permission on hosted system")
        pytest.skip("system does not allow access to input devices")

    # emulate key presses
    _container.keyboard_service._on_key_callback(KeyboardEvent(event_type=KEY_DOWN, name="b", scan_code=None))

    # check subprocess.check_call was invoked
    mock_run.assert_called()
