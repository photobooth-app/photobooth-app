import logging
import time

import pytest

from photobooth.container import Container, container
from photobooth.services.config import appconfig

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def _container() -> Container:
    container.start()
    yield container
    container.stop()


def test_disabled(_container: Container):
    """should just fail in silence if disabled but app triggers some presets"""

    appconfig.hardwareinputoutput.wled_enabled = False

    try:
        _container.wled_service.start()

        # test this, because should be ignored, no error
        _container.wled_service.preset_standby()

    except Exception as exc:
        raise AssertionError("init failed") from exc


def test_enabled_nonexistentserialport(_container: Container):
    """should just fail in silence if disabled but app triggers some presets"""

    appconfig.hardwareinputoutput.wled_enabled = True
    appconfig.hardwareinputoutput.wled_serial_port = "nonexistentserialport"

    # start service on nonexistant port shall not fail - it tries to reconnect and never shall fail
    _container.wled_service.start()


def test_restart_class(_container: Container):
    logger.debug("getting service, starting resource")
    _container.wled_service.start()

    logger.debug("shutdown resource")
    _container.wled_service.stop()

    logger.debug("getting service, starting resource again")
    _container.wled_service.start()


def test_change_presets(_container: Container):
    logger.debug("getting service, starting resource")

    time.sleep(0.1)

    _container.wled_service.preset_thrill()
    time.sleep(0.5)
    _container.wled_service.preset_shoot()
    time.sleep(0.5)
    _container.wled_service.preset_record()
    time.sleep(0.5)
    _container.wled_service.preset_standby()
    time.sleep(0.1)
