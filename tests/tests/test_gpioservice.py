import logging
import time
from unittest.mock import patch

import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory

from photobooth.container import Container, container
from photobooth.services.config import appconfig
from photobooth.services.gpioservice import DEBOUNCE_TIME, HOLD_TIME_REBOOT, HOLD_TIME_SHUTDOWN


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


Device.pin_factory = MockFactory()
logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Container:
    # setup
    container.start()
    # create one image to ensure there is at least one
    if container.mediacollection_service.number_of_images == 0:
        container.processing_service.trigger_action("image", 0)
        container.processing_service.wait_until_job_finished()

    # force register listener for testing purposes
    container.gpio_service.init_io()

    # deliver
    yield container
    container.stop()


@patch("subprocess.check_call")
def test_button_shutdown(mock_check_call, _container: Container):
    # emulate gpio active low driven (simulates button press)
    _container.gpio_service.shutdown_btn.pin.drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME or 0.0 + HOLD_TIME_SHUTDOWN + 0.5)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


@patch("subprocess.check_call")
def test_button_reboot(mock_check_call, _container: Container):
    # emulate gpio active low driven (simulates button press)
    _container.gpio_service.reboot_btn.pin.drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME or 0.0 + HOLD_TIME_REBOOT + 0.5)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


def test_button_action_buttons(_container: Container):
    # modify config
    # services.config().hardwareinputoutput.gpio_enabled = True

    with patch.object(_container.processing_service, "_start_job"):
        # emulate gpio active low driven (simulates button press)
        for action_button in _container.gpio_service.action_btns:
            action_button.pin.drive_low()

            # wait debounce time
            time.sleep(DEBOUNCE_TIME or 0.0 + 0.5)

        _container.processing_service._start_job.assert_called()

        assert len(_container.gpio_service.action_btns) == _container.processing_service._start_job.call_count


@patch("subprocess.run")
def test_button_print(mock_run, _container: Container):
    appconfig.hardwareinputoutput.printing_enabled = True

    # emulate gpio active low driven (simulates button press)
    for print_button in _container.gpio_service.print_btns:
        print_button.pin.drive_low()

        # wait debounce time
        time.sleep(DEBOUNCE_TIME or 0.0 + 0.5)

        # emulate print finished, to avoid need to wait for blocking time.
        _container.printing_service._last_print_time = None

    mock_run.assert_called()

    assert len(_container.gpio_service.print_btns) == mock_run.call_count
