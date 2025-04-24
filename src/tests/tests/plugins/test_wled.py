import logging
import time

import pytest

from photobooth.plugins.wled.wled import Wled, WledConfig, WledPreset

logger = logging.getLogger(name=None)


## check skip if wrong platform
if not WledConfig().wled_serial_port:
    pytest.skip("no serial port defined, skipping test", allow_module_level=True)


@pytest.fixture()
def wled_plugin():
    # setup
    ws = Wled()

    yield ws


def test_disabled(wled_plugin: Wled):
    """should just fail in silence if disabled but app triggers some presets"""
    wled_plugin._config.wled_enabled = False
    wled_plugin._config.wled_serial_port = ""

    wled_plugin.start()

    # test this, because should be ignored, no error
    wled_plugin.send_preset(WledPreset.STANDBY)


def test_enabled_nonexistentserialport(wled_plugin: Wled):
    """should just fail in silence if disabled but app triggers some presets"""

    wled_plugin._config.wled_enabled = True
    wled_plugin._config.wled_serial_port = "nonexistentserialport"

    # start service on nonexistant port shall not fail - it tries to reconnect and never shall fail
    wled_plugin.start()
    wled_plugin.stop()


def test_enabled_emptyport(wled_plugin: Wled):
    """should just fail in silence if disabled but app triggers some presets"""

    wled_plugin._config.wled_enabled = True
    wled_plugin._config.wled_serial_port = ""

    # start service on nonexistant port shall not fail - it tries to reconnect and never shall fail
    wled_plugin.start()
    wled_plugin.wait_until_ready()


def test_restart_class(wled_plugin: Wled):
    wled_plugin.start()
    # no waiting, the service thread is probably still starting up but we ASK to stop it right away...
    wled_plugin.stop()
    wled_plugin.start()
    wled_plugin.wait_until_ready()
    wled_plugin.stop()


def test_change_presets(wled_plugin: Wled):
    wled_plugin.start()
    logger.debug("getting service, starting resource")

    if not wled_plugin.wait_until_ready():
        raise AssertionError("service did not get up")

    wled_plugin.send_preset(WledPreset.THRILL)
    time.sleep(0.5)
    wled_plugin.send_preset(WledPreset.SHOOT)
    time.sleep(0.5)
    wled_plugin.send_preset(WledPreset.RECORD)
    time.sleep(0.5)
    wled_plugin.send_preset(WledPreset.STANDBY)
    time.sleep(0.1)
