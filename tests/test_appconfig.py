"""
Testing virtual camera Backend
"""
import logging
from importlib import reload

import photobooth.services.config
from photobooth.services.config import AppConfig, appconfig

reload(photobooth.services.config)  # reset config to defaults.
logger = logging.getLogger(name=None)


def test_appconfig_singleton():
    # modify config:
    appconfig.common.DEBUG_LEVEL = 99
    assert appconfig.common.DEBUG_LEVEL == 99
    assert not AppConfig().common.DEBUG_LEVEL == 99


def test_appconfig_factory():
    # modify config:
    appconfig.common.DEBUG_LEVEL = 99
    assert not AppConfig().common.DEBUG_LEVEL == 99
