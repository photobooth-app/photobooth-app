import logging
import time
from unittest.mock import patch

import pytest
from dependency_injector import providers
from gpiozero import Device
from gpiozero.pins.mock import MockFactory
from pymitter import EventEmitter

from photobooth.appconfig import AppConfig
from photobooth.services.backends.containers import BackendsContainer
from photobooth.services.containers import ServicesContainer
from photobooth.services.gpioservice import DEBOUNCE_TIME, HOLD_TIME_REBOOT, HOLD_TIME_SHUTDOWN, GpioService

Device.pin_factory = MockFactory()


logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def services() -> GpioService:
    # setup
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
    # force register listener for testing purposes
    services.gpio_service()._register_listener()

    # deliver
    yield services


@patch("subprocess.check_call")
def test_button_shutdown(mock_check_call, services: ServicesContainer):
    # emulate gpio active low driven (simulates button press)
    services.gpio_service().shutdown_btn.pin.drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME + HOLD_TIME_SHUTDOWN + 0.1)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


@patch("subprocess.check_call")
def test_button_reboot(mock_check_call, services: ServicesContainer):
    # emulate gpio active low driven (simulates button press)
    services.gpio_service().reboot_btn.pin.drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME + HOLD_TIME_REBOOT + 0.1)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


def test_button_take1pic(services: ServicesContainer):
    # modify config
    # services.config().hardwareinputoutput.gpio_enabled = True

    with patch.object(services.processing_service(), "evt_chose_1pic_get"):
        # emulate gpio active low driven (simulates button press)
        services.gpio_service().take1pic_btn.pin.drive_low()

        # wait debounce time
        time.sleep(DEBOUNCE_TIME + 0.1)

        services.processing_service().evt_chose_1pic_get.assert_called()
