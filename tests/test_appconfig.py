"""
Testing virtual camera Backend
"""
import logging

from photobooth.services.config import AppConfig, appconfig

appconfig.__dict__.update(AppConfig())
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
