import logging
import time

import pytest

from photobooth.containers import ApplicationContainer
from photobooth.services.containers import ServicesContainer

logger = logging.getLogger(name=None)


@pytest.fixture()
def services() -> ServicesContainer:
    # setup
    application_container = ApplicationContainer()

    services = application_container.services()

    # deliver
    yield services
    services.shutdown_resources()


def test_disabled(services: ServicesContainer):
    """should just fail in silence if disabled but app triggers some presets"""

    services.config().hardwareinputoutput.wled_enabled = False

    try:
        wled_service = services.wled_service()

        # test this, because should be ignored, no error
        wled_service.preset_standby()

    except Exception as exc:
        raise AssertionError("init failed") from exc


def test_enabled_nonexistentserialport(services: ServicesContainer):
    """should just fail in silence if disabled but app triggers some presets"""

    services.config().hardwareinputoutput.wled_enabled = True
    services.config().hardwareinputoutput.wled_serial_port = "nonexistentserialport"

    # start service on nonexistant port shall not fail - it tries to reconnect and never shall fail
    services.wled_service()


def test_restart_class(services: ServicesContainer):
    logger.debug("getting service, starting resource")
    services.wled_service()

    logger.debug("shutdown resource")
    services.wled_service.shutdown()

    logger.debug("getting service, starting resource again")
    services.wled_service()


def test_change_presets(services: ServicesContainer):
    logger.debug("getting service, starting resource")
    wled_service = services.wled_service()

    time.sleep(1)

    wled_service.preset_thrill()
    time.sleep(2)
    wled_service.preset_shoot()
    time.sleep(1)
    wled_service.preset_standby()
    time.sleep(0.5)
