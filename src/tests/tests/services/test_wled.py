import logging
import time

import pytest

from photobooth.services.config import appconfig
from photobooth.services.wled import WledService

logger = logging.getLogger(name=None)


@pytest.fixture()
def wled_service():
    # setup
    ws = WledService()

    yield ws


def test_disabled(wled_service: WledService):
    """should just fail in silence if disabled but app triggers some presets"""
    wled_service.start()

    # test this, because should be ignored, no error
    wled_service.preset_standby()


def test_enabled_nonexistentserialport(wled_service: WledService):
    """should just fail in silence if disabled but app triggers some presets"""

    appconfig.hardwareinputoutput.wled_enabled = True
    appconfig.hardwareinputoutput.wled_serial_port = "nonexistentserialport"

    # start service on nonexistant port shall not fail - it tries to reconnect and never shall fail
    wled_service.start()


def test_enabled_emptyport(wled_service: WledService):
    """should just fail in silence if disabled but app triggers some presets"""

    appconfig.hardwareinputoutput.wled_enabled = True
    appconfig.hardwareinputoutput.wled_serial_port = ""

    # start service on nonexistant port shall not fail - it tries to reconnect and never shall fail
    wled_service.start()


def test_restart_class(wled_service: WledService):
    logger.debug("getting service, starting resource")
    wled_service.start()

    logger.debug("shutdown resource")
    wled_service.stop()

    logger.debug("getting service, starting resource again")
    wled_service.start()


def test_change_presets(wled_service: WledService):
    logger.debug("getting service, starting resource")

    time.sleep(0.1)

    wled_service.preset_thrill()
    time.sleep(0.5)
    wled_service.preset_shoot()
    time.sleep(0.5)
    wled_service.preset_record()
    time.sleep(0.5)
    wled_service.preset_standby()
    time.sleep(0.1)
