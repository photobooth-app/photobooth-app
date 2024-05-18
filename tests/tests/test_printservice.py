import logging
import time
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
    """service is disabled by default - test for that."""

    appconfig.hardwareinputoutput.printing_enabled = False

    _container.stop()
    _container.start()

    # get the newest mediaitem
    latest_mediaitem = _container.mediacollection_service.db_get_most_recent_mediaitem()

    with pytest.raises(ConnectionRefusedError):
        _container.printing_service.print(latest_mediaitem)

    assert mock_run.assert_not_called


@patch("subprocess.run")
def test_print_image(mock_run, _container: Container):
    """enable service and try to print"""

    appconfig.hardwareinputoutput.printing_enabled = True

    _container.stop()
    _container.start()

    # get the newest mediaitem
    latest_mediaitem = _container.mediacollection_service.db_get_most_recent_mediaitem()

    logger.info(f"test to print {str(latest_mediaitem)}")

    _container.printing_service.print(latest_mediaitem)

    # check subprocess.run was invoked
    mock_run.assert_called()


@patch("subprocess.run")
def test_print_image_blocked(mock_run, _container: Container):
    """enable service and try to print, check that it repsonds blocking correctly"""

    appconfig.hardwareinputoutput.printing_enabled = True

    _container.stop()
    _container.start()

    # get the newest mediaitem
    latest_mediaitem = _container.mediacollection_service.db_get_most_recent_mediaitem()

    # two prints issued

    _container.printing_service.print(latest_mediaitem)
    while _container.printing_service.is_blocked():
        logger.debug("waiting for printer to unblock")
        time.sleep(1)

    _container.printing_service.print(latest_mediaitem)
    time.sleep(1)
    with pytest.raises(BlockingIOError):
        _container.printing_service.print(latest_mediaitem)

    # check subprocess.run was invoked
    mock_run.assert_called()
