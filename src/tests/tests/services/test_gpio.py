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


def test_pinhandler_singleton():
    pinhandler1_1 = PinHandler(1, 1)
    pinhandler1_2 = PinHandler(1, 1)
    pinhandler2_1 = PinHandler(2, 1)

    assert pinhandler1_1 is pinhandler1_2
    assert pinhandler1_1 is not pinhandler2_1


@patch("subprocess.check_call")
def test_button_shutdown(mock_check_call, _container: Container):
    # assert _container.gpio_service.shutdown_btn
    # emulate gpio active low driven (simulates button press)
    # cast(MockPin, _container.gpio_service.shutdown_btn.pin).drive_low()
    cast(MockPin, PinHandler(appconfig.hardwareinputoutput.gpio_pin_shutdown).button.pin).drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME + HOLD_TIME_SHUTDOWN + 0.5)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


@patch("subprocess.check_call")
def test_button_reboot(mock_check_call, _container: Container):
    # assert _container.gpio_service.reboot_btn
    # emulate gpio active low driven (simulates button press)
    cast(MockPin, PinHandler(appconfig.hardwareinputoutput.gpio_pin_reboot).button.pin).drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME + HOLD_TIME_REBOOT + 0.5)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


def test_button_action_buttons(_container: Container):
    # modify config

    with patch.object(_container.processing_service, "_start_job") as mock:
        # emulate gpio active low driven (simulates button press)
        for action_type in get_args(ActionType):
            for config in getattr(appconfig.actions, action_type):
                cast(MockPin, PinHandler(config.trigger.gpio_trigger.pin).button.pin).drive_low()

                # wait debounce time
                time.sleep(DEBOUNCE_TIME + 0.5)

                mock.assert_called_once()
                mock.reset_mock()

        # assert calls == mock.call_count


@patch("subprocess.run")
def test_button_share(mock_run: MagicMock, _container: Container):
    appconfig.share.sharing_enabled = True

    # emulate gpio active low driven (simulates button press)
    for share_button in _container.gpio_service.share_btns:
        cast(MockPin, share_button.pin).drive_low()

        # wait debounce time
        time.sleep(DEBOUNCE_TIME + 0.5)

    mock_run.assert_called()

    assert len(_container.gpio_service.share_btns) == mock_run.call_count
