import logging
import time
from collections.abc import Generator
from typing import cast, get_args
from unittest.mock import MagicMock, patch

import pytest
from gpiozero.pins.mock import MockPin

from photobooth.appconfig import appconfig
from photobooth.container import Container, container
from photobooth.services.gpio import DEBOUNCE_TIME, HOLD_TIME_REBOOT, HOLD_TIME_SHUTDOWN, PinHandler
from photobooth.services.processing import ActionType

logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Generator[Container, None, None]:
    # setup

    # tests fail if not enabled
    appconfig.hardwareinputoutput.gpio_enabled = True

    container.start()

    # deliver
    yield container
    container.stop()


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
    pinhandler2_1 = PinHandler(2, 1)

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
def test_button_shutdown(mock_check_call, _container: Container):
    ph = PinHandler(appconfig.hardwareinputoutput.gpio_pin_shutdown)
    assert ph  # only assert because we assume always to have this configured and tested

    cast(MockPin, ph.button.pin).drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME + HOLD_TIME_SHUTDOWN + 0.5)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


@patch("subprocess.check_call")
def test_button_reboot(mock_check_call, _container: Container):
    # assert _container.gpio_service.reboot_btn
    # emulate gpio active low driven (simulates button press)
    ph = PinHandler(appconfig.hardwareinputoutput.gpio_pin_reboot)
    assert ph  # only assert because we assume always to have this configured and tested

    cast(MockPin, ph.button.pin).drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME + HOLD_TIME_REBOOT + 0.5)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


def test_button_action_buttons(_container: Container):
    for action_type in get_args(ActionType):
        with patch.object(_container.processing_service, "trigger_action") as mock:
            for config in getattr(appconfig.actions, action_type):
                ph = PinHandler(config.trigger.gpio_trigger.pin)
                if ph:
                    cast(MockPin, ph.button.pin).drive_low()

                # wait debounce time
                time.sleep(DEBOUNCE_TIME + 0.1)

                enabled_triggers = sum([True for cfg in getattr(appconfig.actions, action_type) if cfg.trigger.gpio_trigger.pin != ""])
                assert mock.call_count > 0  # ensure at least one was tested
                assert enabled_triggers == mock.call_count


@patch("subprocess.run")
def test_button_share(mock_run: MagicMock, _container: Container):
    appconfig.share.sharing_enabled = True

    for config in appconfig.share.actions:
        ph = PinHandler(config.trigger.gpio_trigger.pin)
        if ph:
            cast(MockPin, ph.button.pin).drive_low()

        # wait debounce time
        time.sleep(DEBOUNCE_TIME + 0.1)

    enabled_triggers = sum([True for cfg in appconfig.share.actions if cfg.trigger.gpio_trigger.pin != ""])
    assert mock_run.call_count > 0  # ensure at least one was tested
    assert enabled_triggers == mock_run.call_count
