import logging
import time
from unittest.mock import patch

import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory

from photobooth.containers import ApplicationContainer
from photobooth.services.config import appconfig
from photobooth.services.containers import ServicesContainer
from photobooth.services.gpioservice import DEBOUNCE_TIME, HOLD_TIME_REBOOT, HOLD_TIME_SHUTDOWN

Device.pin_factory = MockFactory()


logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def services() -> ServicesContainer:
    # setup
    application_container = ApplicationContainer()

    services = application_container.services()
    # force register listener for testing purposes
    services.gpio_service().init_io()

    # deliver
    yield services
    services.shutdown_resources()


@patch("subprocess.check_call")
def test_button_shutdown(mock_check_call, services: ServicesContainer):
    # emulate gpio active low driven (simulates button press)
    services.gpio_service().shutdown_btn.pin.drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME or 0.0 + HOLD_TIME_SHUTDOWN + 0.2)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


@patch("subprocess.check_call")
def test_button_reboot(mock_check_call, services: ServicesContainer):
    # emulate gpio active low driven (simulates button press)
    services.gpio_service().reboot_btn.pin.drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME or 0.0 + HOLD_TIME_REBOOT + 0.2)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


def test_button_take1pic(services: ServicesContainer):
    # modify config
    # services.config().hardwareinputoutput.gpio_enabled = True

    with patch.object(services.processing_service(), "start_job_1pic"):
        # emulate gpio active low driven (simulates button press)
        services.gpio_service().take1pic_btn.pin.drive_low()

        # wait debounce time
        time.sleep(DEBOUNCE_TIME or 0.0 + 0.2)

        services.processing_service().start_job_1pic.assert_called()


def test_button_takecollage(services: ServicesContainer):
    # modify config
    # services.config().hardwareinputoutput.gpio_enabled = True

    with patch.object(services.processing_service(), "start_job_collage"):
        # emulate gpio active low driven (simulates button press)
        services.gpio_service().takecollage_btn.pin.drive_low()

        # wait debounce time
        time.sleep(DEBOUNCE_TIME or 0.0 + 0.2)

        services.processing_service().start_job_collage.assert_called()


@patch("subprocess.run")
def test_button_print(mock_run, services: ServicesContainer):
    appconfig.hardwareinputoutput.printing_enabled = True

    # emulate gpio active low driven (simulates button press)
    services.gpio_service().print_recent_item_btn.pin.drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME or 0.0 + HOLD_TIME_REBOOT + 0.2)

    # check subprocess.check_call was invoked
    mock_run.assert_called()
