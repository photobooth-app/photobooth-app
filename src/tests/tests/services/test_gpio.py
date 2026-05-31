import logging
import time
from collections.abc import Generator
from typing import cast, get_args
from unittest.mock import MagicMock, patch

import pytest
from gpiozero.pins.mock import MockPin

from photobooth.appconfig import appconfig
from photobooth.services.config.groups.hardwareinputoutput import GroupHardwareInputOutput
from photobooth.services.gpio import DEBOUNCE_TIME, HOLD_TIME_REBOOT, HOLD_TIME_SHUTDOWN, GpioService, PinHandler
from photobooth.services.processing import ActionType

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def gpio_service():
    # ensure GPIO is enabled
    cfg = GroupHardwareInputOutput(gpio_enabled=True)

    # mock dependencies
    processing = MagicMock()
    processing.is_occupied.return_value = False
    share = MagicMock()
    mediacollection = MagicMock()

    service = GpioService(processing, share, mediacollection, cfg)

    # reset PinHandler global state
    PinHandler._teardown()

    service.start()

    yield service, processing, share, mediacollection

    service.stop()


@pytest.fixture(scope="function")
def pinhandler1() -> Generator[PinHandler, None, None]:
    PinHandler._teardown()

    pinhandler1_1 = PinHandler(1, 0.3)
    assert pinhandler1_1
    yield pinhandler1_1

    PinHandler._teardown()


def test_pinhandler_singleton(pinhandler1: PinHandler):
    pinhandler1_1 = pinhandler1
    pinhandler1_2 = PinHandler(1, 1)
    pinhandler2_1 = PinHandler(3, 1)

    assert pinhandler1_1 is pinhandler1_2
    assert pinhandler1_1 is not pinhandler2_1


def test_pinhandler_register_two_callbacks(pinhandler1: PinHandler):
    with patch.object(PinHandler, "_handle_pressed") as mock:
        pinhandler1.register_callback("pressed", mock, 1, 1)
        pinhandler1.register_callback("pressed", mock, 1, 2)

        # drive + wait hold time
        cast(MockPin, pinhandler1.button.pin).drive_low()
        time.sleep(DEBOUNCE_TIME + 0.1)

        calllist = mock.call_args_list
        assert calllist[0].args == (1, 1)
        assert calllist[1].args == (1, 2)


def test_pinhandler_register_pressed(pinhandler1: PinHandler):
    with patch.object(PinHandler, "_handle_pressed") as mock:
        pinhandler1.register_callback("pressed", mock, 1, 1)

        # drive + wait hold time
        cast(MockPin, pinhandler1.button.pin).drive_low()
        time.sleep(DEBOUNCE_TIME + 0.1)

        assert mock.call_args.args == (1, 1)


def test_pinhandler_register_released(pinhandler1: PinHandler):
    with patch.object(PinHandler, "_handle_released") as mock:
        pinhandler1.register_callback("released", mock, 1, 1)

        # drive + wait hold time
        cast(MockPin, pinhandler1.button.pin).drive_low()
        time.sleep(DEBOUNCE_TIME + 0.1)
        cast(MockPin, pinhandler1.button.pin).drive_high()
        time.sleep(DEBOUNCE_TIME + 0.1)

        assert mock.call_args.args == (1, 1)


def test_pinhandler_register_longpress(pinhandler1: PinHandler):
    with patch.object(PinHandler, "_handle_longpress") as mock:
        pinhandler1.register_callback("longpress", mock, 1, 1)

        # drive + wait hold time
        cast(MockPin, pinhandler1.button.pin).drive_low()
        time.sleep(DEBOUNCE_TIME + 0.3 + 0.1)

        assert mock.call_args.args == (1, 1)


@patch("subprocess.check_call")
def test_button_shutdown(mock_check_call, gpio_service):
    service, processing, share, mediacollection = gpio_service
    ph = PinHandler(service._config.gpio_pin_shutdown)
    assert ph  # only assert because we assume always to have this configured and tested

    cast(MockPin, ph.button.pin).drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME + HOLD_TIME_SHUTDOWN + 0.5)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


@patch("subprocess.check_call")
def test_button_reboot(mock_check_call, gpio_service):
    service, processing, share, mediacollection = gpio_service
    # assert _container.gpio_service.reboot_btn
    # emulate gpio active low driven (simulates button press)
    ph = PinHandler(service._config.gpio_pin_reboot)
    assert ph  # only assert because we assume always to have this configured and tested

    cast(MockPin, ph.button.pin).drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME + HOLD_TIME_REBOOT + 0.5)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


def test_action_buttons(gpio_service):
    service, processing, share, mediacollection = gpio_service

    for action_type in get_args(ActionType):
        for index, config in enumerate(getattr(appconfig.actions, action_type)):
            pin = config.trigger.gpio_trigger.pin
            if not pin:
                continue

            ph = PinHandler(pin)
            assert ph

            # simulate button press
            cast(MockPin, ph.button.pin).drive_low()
            time.sleep(DEBOUNCE_TIME + 0.1)

            processing.trigger_action.assert_any_call(action_type, index)


def test_button_share(gpio_service):
    service, processing, share, mediacollection = gpio_service

    for index, config in enumerate(appconfig.share.actions):
        ph = PinHandler(config.trigger.gpio_trigger.pin)
        if ph:
            cast(MockPin, ph.button.pin).drive_low()

            # wait debounce time
            time.sleep(DEBOUNCE_TIME + 0.1)
            share.share.assert_any_call(mediacollection.get_item_latest(), index)

    assert share.share.called
