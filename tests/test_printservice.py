import logging
import time
from unittest.mock import patch

import pytest

from photobooth.containers import ApplicationContainer
from photobooth.services.containers import ServicesContainer

logger = logging.getLogger(name=None)


@pytest.fixture()
def services() -> ServicesContainer:
    # setup
    application_container = ApplicationContainer()

    services = application_container.services()

    # create one image to ensure there is at least one
    services.processing_service().start_job_1pic()

    # deliver
    yield services
    services.shutdown_resources()


def test_print_service_disabled(services: ServicesContainer):
    """service is disabled by default - test for that."""

    # init when called
    printing_service = services.printing_service()

    # get the newest mediaitem
    latest_mediaitem = services.mediacollection_service().db_get_most_recent_mediaitem()

    with pytest.raises(ConnectionRefusedError):
        printing_service.print(latest_mediaitem)


@patch("subprocess.run")
def test_print_image(mock_run, services: ServicesContainer):
    """enable service and try to print"""

    services.config().hardwareinputoutput.printing_enabled = True

    # init when called
    printing_service = services.printing_service()

    # get the newest mediaitem
    latest_mediaitem = services.mediacollection_service().db_get_most_recent_mediaitem()

    logger.info(f"test to print {str(latest_mediaitem)}")

    printing_service.print(latest_mediaitem)

    # check subprocess.run was invoked
    mock_run.assert_called()


@patch("subprocess.run")
def test_print_image_blocked(mock_run, services: ServicesContainer):
    """enable service and try to print, check that it repsonds blocking correctly"""

    services.config().hardwareinputoutput.printing_enabled = True
    services.config().hardwareinputoutput.printing_blocked_time = 2

    # init when called
    printing_service = services.printing_service()

    # get the newest mediaitem
    latest_mediaitem = services.mediacollection_service().db_get_most_recent_mediaitem()

    # two prints issued that should not block because 3s>2s
    printing_service.print(latest_mediaitem)
    time.sleep(3)
    printing_service.print(latest_mediaitem)
    time.sleep(1)
    with pytest.raises(BlockingIOError):
        printing_service.print(latest_mediaitem)

    # check subprocess.run was invoked
    mock_run.assert_called()
