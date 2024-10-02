import logging
import time
from dataclasses import asdict
from unittest.mock import patch

import pytest

from photobooth.container import Container, container
from photobooth.services.config import appconfig

logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Container:
    container.start()
    yield container
    container.stop()


@patch("subprocess.run")
def test_print_service_disabled(mock_run, _container: Container):
    """test answer when disabled globally"""

    appconfig.share.sharing_enabled = False
    container.share_service._last_print_time = None  # reset

    # get the newest mediaitem
    latest_mediaitem = _container.mediacollection_service.db_get_most_recent_mediaitem()

    with pytest.raises(ConnectionRefusedError):
        _container.share_service.share(latest_mediaitem)

    assert mock_run.assert_not_called


@patch("subprocess.run")
def test_print_image(mock_run, _container: Container):
    """enable service and try to print"""

    appconfig.share.sharing_enabled = True
    container.share_service._last_print_time = None  # reset
    appconfig.share.actions[0].processing.max_shares = 0

    # get the newest mediaitem
    latest_mediaitem = _container.mediacollection_service.db_get_most_recent_mediaitem()

    logger.info(f"test to print {str(latest_mediaitem)}")

    _container.share_service.share(latest_mediaitem)

    # check subprocess.run was invoked
    mock_run.assert_called_once()


@patch("subprocess.run")
def test_print_image_blocked(mock_run, _container: Container):
    """enable service and try to print, check that it repsonds blocking correctly"""

    appconfig.share.sharing_enabled = True
    container.share_service._last_print_time = None  # reset
    appconfig.share.actions[0].processing.max_shares = 0

    # get the newest mediaitem
    latest_mediaitem = _container.mediacollection_service.db_get_most_recent_mediaitem()

    # two prints issued

    _container.share_service.share(latest_mediaitem)
    while _container.share_service.is_time_blocked():
        logger.debug("waiting for printer to unblock")
        time.sleep(1)

    _container.share_service.share(latest_mediaitem)
    time.sleep(1)
    with pytest.raises(BlockingIOError):
        _container.share_service.share(latest_mediaitem)

    # check subprocess.run was invoked
    assert mock_run.call_count == 2


@patch("subprocess.run")
def test_is_limited_no_limit(mock_run, _container: Container):
    """Test is_limited when max_shares is 0, meaning no limit."""

    # Setup
    appconfig.share.sharing_enabled = True
    container.share_service._last_print_time = None  # reset
    config_index = 0
    appconfig.share.actions[config_index].name = "share_action"
    appconfig.share.actions[config_index].processing.max_shares = 0
    _container.information_service._stats_counter.limits = {appconfig.share.actions[config_index].name: 5}

    latest_mediaitem = _container.mediacollection_service.db_get_most_recent_mediaitem()
    _container.share_service.share(latest_mediaitem)

    # command was called, means quota not exceeded.
    mock_run.assert_called_once()


@patch("subprocess.run")
def test_is_limited_exceeded(mock_run, _container: Container):
    """Test is_limited when max_shares is 0, meaning no limit."""

    # Setup
    appconfig.share.sharing_enabled = True
    container.share_service._last_print_time = None  # reset
    config_index = 0
    appconfig.share.actions[config_index].name = "share_action"
    appconfig.share.actions[config_index].processing.max_shares = 5
    _container.information_service._stats_counter.limits = {appconfig.share.actions[config_index].name: 5}

    # command was not called, means quota exceeded.

    print(appconfig.share.actions[config_index])
    print(asdict(_container.information_service._stats_counter))
    mock_run.assert_not_called()
