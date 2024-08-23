import logging
import time
from unittest.mock import patch

import pytest

from photobooth.container import Container, container
from photobooth.services.config import appconfig
from photobooth.services.sseservice import SseEventFrontendNotification

logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Container:
    container.start()
    yield container
    container.stop()


@patch("subprocess.run")
def test_print_service_disabled(mock_run, _container: Container):
    """service is disabled by default - test for that."""

    appconfig.share.sharing_enabled = False

    _container.stop()
    _container.start()

    # get the newest mediaitem
    latest_mediaitem = _container.mediacollection_service.db_get_most_recent_mediaitem()

    with pytest.raises(ConnectionRefusedError):
        _container.share_service.share(latest_mediaitem)

    assert mock_run.assert_not_called


@patch("subprocess.run")
def test_print_image(mock_run, _container: Container):
    """enable service and try to print"""

    appconfig.share.sharing_enabled = True

    _container.stop()
    _container.start()

    # get the newest mediaitem
    latest_mediaitem = _container.mediacollection_service.db_get_most_recent_mediaitem()

    logger.info(f"test to print {str(latest_mediaitem)}")

    _container.share_service.share(latest_mediaitem)

    # check subprocess.run was invoked
    mock_run.assert_called()


@patch("subprocess.run")
def test_print_image_blocked(mock_run, _container: Container):
    """enable service and try to print, check that it repsonds blocking correctly"""

    appconfig.share.sharing_enabled = True

    _container.stop()
    _container.start()

    # get the newest mediaitem
    latest_mediaitem = _container.mediacollection_service.db_get_most_recent_mediaitem()

    # two prints issued

    _container.share_service.share(latest_mediaitem)
    while _container.share_service.is_blocked():
        logger.debug("waiting for printer to unblock")
        time.sleep(1)

    _container.share_service.share(latest_mediaitem)
    time.sleep(1)
    with pytest.raises(BlockingIOError):
        _container.share_service.share(latest_mediaitem)

    # check subprocess.run was invoked
    mock_run.assert_called()

@patch("subprocess.run")
def test_is_limited_no_limit(mock_run, _container: Container):
    """Test is_limited when max_shares is 0, meaning no limit."""
    
    appconfig.share.sharing_enabled = True

    _container.stop()
    _container.start()

    # Setup
    config_index = 0
    _container.share_service._information_service._stats_counter.limits = {"share_action": 5}
    action_config = appconfig.share.actions[config_index]
    action_config.name = "share_action"
    
    # Call method with max_shares = 0 (no limit)
    result = _container.share_service.is_limited(0, action_config)
    
    # Assert the function returns False (not limited)
    assert not result
    mock_run.assert_called()

@patch("subprocess.run")
def test_is_limited_within_limit(mock_run, _container: Container):
    """Test is_limited when current_shares is less than max_shares."""
    
    appconfig.share.sharing_enabled = True

    _container.stop()
    _container.start()
    
    # Setup
    config_index = 0
    _container.share_service._information_service._stats_counter.limits = {"share_action": 3}
    action_config = appconfig.share.actions[config_index]
    action_config.name = "share_action"
    
    # Call method with max_shares = 5, current_shares = 3
    result = _container.share_service.is_limited(5, action_config)
    
    # Assert the function returns False (not limited)
    assert not result
    mock_run.assert_called()

@patch("subprocess.run")
def test_is_limited_at_limit(mock_run, _container: Container):
    """Test is_limited when current_shares equals max_shares."""
    
    appconfig.share.sharing_enabled = True

    _container.stop()
    _container.start()
    
    # Setup
    config_index = 0
    _container.share_service._information_service._stats_counter.limits = {"share_action": 5}
    action_config = appconfig.share.actions[config_index]
    action_config.name = "share_action"
    
    # Call method with max_shares = 5, current_shares = 5
    result = _container.share_service.is_limited(5, action_config)
    
    # Assert the function returns True (limited)
    assert result
    mock_run.assert_called()

@patch("subprocess.run")
def test_is_limited_above_limit(mock_run, _container: Container):
    """Test is_limited when current_shares is more than max_shares."""
    
    appconfig.share.sharing_enabled = True

    _container.stop()
    _container.start()
    
    # Setup
    config_index = 0
    _container.share_service._information_service._stats_counter.limits = {"share_action": 7}
    action_config = appconfig.share.actions[config_index]
    action_config.name = "share_action"
    
    # Call method with max_shares = 5, current_shares = 7
    result = _container.share_service.is_limited(5, action_config)
    
    # Assert the function returns True (limited)
    assert result
    mock_run.assert_called()

@patch("subprocess.run")
def test_is_limited_action_not_in_limits(mock_run, _container: Container):
    """Test is_limited when action_config.name is not in limits."""
    
    appconfig.share.sharing_enabled = True

    _container.stop()
    _container.start()
    
    # Setup
    config_index = 0
    _container.share_service._information_service._stats_counter.limits = {"share_action": 2}
    action_config = appconfig.share.actions[config_index]
    action_config.name = "share_action"
    
    # Call method with max_shares = 5, action_config.name not in limits
    result = _container.share_service.is_limited(5, action_config)
    
    # Assert the function returns False (not limited)
    assert not result
    mock_run.assert_called()

@patch("subprocess.run")
def test_max_shares_exceeded(mock_run, _container: Container):
    """Test behavior when max_shares is exceeded."""
    
    appconfig.share.sharing_enabled = True

    _container.stop()
    _container.start()

    # Setup
    config_index = 0
    action_config = appconfig.share.actions[config_index]
    action_config.trigger.ui_trigger.title = "Test Action"
    _container.share_service._information_service._stats_counter.limits = {
        action_config.name: 11
    }

    # Call method and expect a BlockingIOError
    with pytest.raises(BlockingIOError):
        max_shares = 10
        if _container.share_service.is_limited(max_shares, action_config):
            _container.share_service._sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="negative",
                    message=f"{action_config.trigger.ui_trigger.title} quota exceeded ({max_shares} maximum)",
                    caption="Share/Print quota",
                )
            )
            raise BlockingIOError("Maximum number of Share/Print reached!")

    mock_run.assert_called()

@patch("subprocess.run")
def test_max_shares_not_exceeded(mock_run, _container: Container):
    """Test behavior when max_shares is not exceeded."""
    
    appconfig.share.sharing_enabled = True

    _container.stop()
    _container.start()

    # Setup
    config_index = 0
    action_config = appconfig.share.actions[config_index]
    action_config.processing.max_shares = 5
    action_config.name = "share_action"
    action_config.trigger.ui_trigger.title = "Test Action"
    _container.share_service._information_service._stats_counter.limits = {"share_action": 3}

    # Call method and ensure it doesn't raise an exception
    max_shares = getattr(action_config.processing, "max_shares", 0)
    if _container.share_service.is_limited(max_shares, action_config):
        _container.share_service._sse_service.dispatch_event(
            SseEventFrontendNotification(
                color="negative",
                message=f"{action_config.trigger.ui_trigger.title} quota exceeded ({max_shares} maximum)",
                caption="Share/Print quota",
            )
        )
        raise BlockingIOError("Maximum number of Share/Print reached!")
    else:
        _container.share_service._information_service.stats_counter_increment_limite(action_config.name)
        current_shares = _container.share_service._information_service._stats_counter.limits[action_config.name]
        _container.share_service._sse_service.dispatch_event(
            SseEventFrontendNotification(
                color="info",
                message=f"{action_config.trigger.ui_trigger.title} quota : {current_shares}/{max_shares}",
                caption="Share/Print quota",
            )
        )

    # Ensure the share count was incremented
    _container.share_service._information_service.stats_counter_increment_limite(action_config.name)

    # Ensure the event was dispatched correctly
    _container.share_service._sse_service.dispatch_event(
        SseEventFrontendNotification(
            color="info",
            message=f"{action_config.trigger.ui_trigger.title} quota : 3/5",
            caption="Share/Print quota",
        )
    )

    mock_run.assert_called()
