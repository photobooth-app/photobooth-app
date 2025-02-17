import logging
import time

import pytest

from photobooth.plugins.wled.wled import Wled

logger = logging.getLogger(name=None)


@pytest.fixture()
def wled_plugin():
    # setup
    ws = Wled()

    yield ws


def test_disabled(wled_plugin: Wled):
    """should just fail in silence if disabled but app triggers some presets"""
    wled_plugin.start()

    # test this, because should be ignored, no error
    wled_plugin.preset_standby()


def test_enabled_nonexistentserialport(wled_plugin: Wled):
    """should just fail in silence if disabled but app triggers some presets"""

    wled_plugin._config.wled_enabled = True
    wled_plugin._config.wled_serial_port = "nonexistentserialport"

    # start service on nonexistant port shall not fail - it tries to reconnect and never shall fail
    wled_plugin.start()


def test_enabled_emptyport(wled_plugin: Wled):
    """should just fail in silence if disabled but app triggers some presets"""

    wled_plugin._config.wled_enabled = True
    wled_plugin._config.wled_serial_port = ""

    # start service on nonexistant port shall not fail - it tries to reconnect and never shall fail
    wled_plugin.start()


def test_restart_class(wled_plugin: Wled):
    logger.debug("getting service, starting resource")
    wled_plugin.start()

    logger.debug("shutdown resource")
    wled_plugin.stop()

    logger.debug("getting service, starting resource again")
    wled_plugin.start()


def test_change_presets(wled_plugin: Wled):
    logger.debug("getting service, starting resource")

    time.sleep(0.1)

    wled_plugin.preset_thrill()
    time.sleep(0.5)
    wled_plugin.preset_shoot()
    time.sleep(0.5)
    wled_plugin.preset_record()
    time.sleep(0.5)
    wled_plugin.preset_standby()
    time.sleep(0.1)
