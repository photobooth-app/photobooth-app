import sys
import os
import logging
import pytest
import time
from pymitter import EventEmitter

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from src.configsettings import settings, ConfigSettings
from src.wledservice import WledService

logger = logging.getLogger(name=None)


def test_disabled():
    """should just fail in silence if disabled but app triggers some presets"""

    settings.wled.ENABLED = False

    try:
        ws = WledService(EventEmitter())
        ws.start()
        time.sleep(1)

        # test this, because should be ignored, no error
        ws.preset_standby()

        ws.stop()
    except:
        raise AssertionError("init failed")


def test_enabled_nonexistentserialport():
    """should just fail in silence if disabled but app triggers some presets"""

    settings.wled.ENABLED = True
    settings.wled.SERIAL_PORT = "nonexistentserialport"

    ws = WledService(EventEmitter())
    with pytest.raises(RuntimeError):
        ws.start()

    time.sleep(1)

    ws.stop()


def test_restart_class():
    # from src.wledservice import WledService

    # reset settings to defaults
    settings = ConfigSettings()

    ws = WledService(EventEmitter())
    ws.start()
    time.sleep(1)
    ws.stop()

    # time.sleep(2)
    ws = WledService(EventEmitter())
    ws.start()
    time.sleep(1)
    ws.stop()


def test_change_presets():
    # from src.wledservice import WledService

    # reset settings to defaults
    settings = ConfigSettings()

    ws = WledService(EventEmitter())
    ws.start()

    time.sleep(1)

    ws.preset_thrill()
    time.sleep(2)
    ws.preset_shoot()
    time.sleep(1)
    ws.preset_standby()
    time.sleep(0.5)

    ws.stop()
