import logging
import time
from collections.abc import Generator
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from gpiozero.pins.mock import MockPin

from photobooth.appconfig import appconfig
from photobooth.container import Container, container
from photobooth.services.gpio import DEBOUNCE_TIME, HOLD_TIME_REBOOT, HOLD_TIME_SHUTDOWN

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


@patch("subprocess.check_call")
def test_button_shutdown(mock_check_call, _container: Container):
    assert _container.gpio_service.shutdown_btn
    # emulate gpio active low driven (simulates button press)
    cast(MockPin, _container.gpio_service.shutdown_btn.pin).drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME + HOLD_TIME_SHUTDOWN + 0.5)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


@patch("subprocess.check_call")
def test_button_reboot(mock_check_call, _container: Container):
    assert _container.gpio_service.reboot_btn
    # emulate gpio active low driven (simulates button press)
    cast(MockPin, _container.gpio_service.reboot_btn.pin).drive_low()

    # wait hold time
    time.sleep(DEBOUNCE_TIME + HOLD_TIME_REBOOT + 0.5)

    # check subprocess.check_call was invoked
    mock_check_call.assert_called()


def test_button_action_buttons(_container: Container):
    # modify config
    # services.config().hardwareinputoutput.gpio_enabled = True

    with patch.object(_container.processing_service, "_start_job") as mock:
        # emulate gpio active low driven (simulates button press)
        for action_button in _container.gpio_service.action_btns:
            cast(MockPin, action_button.pin).drive_low()

            # wait debounce time
            time.sleep(DEBOUNCE_TIME + 0.5)

        mock.assert_called()

        assert len(_container.gpio_service.action_btns) == mock.call_count


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
