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
    """should just now fail if forced to disable"""
    try:
        settings.wled.ENABLED = False

        ws = WledService(EventEmitter())
        ws.start()
        time.sleep(1)

        # test this, because should be ignored, no error
        ws.preset_standby()

        ws.stop()
    except:
        raise AssertionError("init failed")


def test_restart_class():
    # from src.wledservice import WledService

    # reset settings to defaults
    settings = ConfigSettings()

    try:
        ws = WledService(EventEmitter())
        ws.start()
        time.sleep(1)
        ws.stop()

        time.sleep(2)
        ws = WledService(EventEmitter())
        ws.start()
        time.sleep(1)
        ws.stop()
    except:
        raise AssertionError("failed")


def test_change_presets():
    # from src.wledservice import WledService

    # reset settings to defaults
    settings = ConfigSettings()

    try:
        ws = WledService(EventEmitter())
        ws.start()

        time.sleep(1)

        ws.preset_countdown()
        time.sleep(2)
        ws.preset_shoot()
        time.sleep(1)
        ws.preset_standby()
        time.sleep(0.5)

        ws.stop()
    except:
        raise AssertionError("failed")
