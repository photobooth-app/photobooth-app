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
    container.processing_service.start_job_1pic()

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
    time.sleep(DEBOUNCE_TIME or 0.0 + HOLD_TIME_SHUTDOWN + 0.2)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


@patch("subprocess.check_call")
def test_button_reboot(mock_check_call, _container: Container):
    # emulate gpio active low driven (simulates button press)
    _container.gpio_service.reboot_btn.pin.drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME or 0.0 + HOLD_TIME_REBOOT + 0.2)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


def test_button_take1pic(_container: Container):
    # modify config
    # services.config().hardwareinputoutput.gpio_enabled = True

    with patch.object(_container.processing_service, "start_job_1pic"):
        # emulate gpio active low driven (simulates button press)
        _container.gpio_service.take1pic_btn.pin.drive_low()

        # wait debounce time
        time.sleep(DEBOUNCE_TIME or 0.0 + 0.2)

        _container.processing_service.start_job_1pic.assert_called()


def test_button_takecollage(_container: Container):
    # modify config
    # services.config().hardwareinputoutput.gpio_enabled = True

    with patch.object(_container.processing_service, "start_job_collage"):
        # emulate gpio active low driven (simulates button press)
        _container.gpio_service.takecollage_btn.pin.drive_low()

        # wait debounce time
        time.sleep(DEBOUNCE_TIME or 0.0 + 0.2)

        _container.processing_service.start_job_collage.assert_called()


def test_button_takeanimation(_container: Container):
    # modify config
    # services.config().hardwareinputoutput.gpio_enabled = True

    with patch.object(_container.processing_service, "start_job_animation"):
        # emulate gpio active low driven (simulates button press)
        _container.gpio_service.takeanimation_btn.pin.drive_low()

        # wait debounce time
        time.sleep(DEBOUNCE_TIME or 0.0 + 0.2)

        _container.processing_service.start_job_animation.assert_called()


@patch("subprocess.run")
def test_button_print(mock_run, _container: Container):
    appconfig.hardwareinputoutput.printing_enabled = True

    # emulate gpio active low driven (simulates button press)
    _container.gpio_service.print_recent_item_btn.pin.drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME or 0.0 + 0.2)

    # check subprocess.check_call was invoked
    mock_run.assert_called()
