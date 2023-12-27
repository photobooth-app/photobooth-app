"""
Testing virtual camera Backend
"""
import logging

import pytest

from photobooth.services.config import AppConfig, appconfig

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=False)
def run_around_tests():
    # slightly modified fixture to ensure it's executed as expected during tests.
    # modify config, autouse fixture resets in next statement and shall give default values.
    appconfig.common.DEBUG_LEVEL = 98

    yield

    appconfig.reset_defaults()

    assert appconfig.common.DEBUG_LEVEL == AppConfig().common.DEBUG_LEVEL


def test_appconfig_singleton():
    # modify config:
    appconfig.common.DEBUG_LEVEL = 99
    assert appconfig.common.DEBUG_LEVEL == 99
    assert not AppConfig().common.DEBUG_LEVEL == 99


def test_appconfig_singleton_reset_defaults_manually():
    # modify config:
    appconfig.common.DEBUG_LEVEL = 99
    assert appconfig.common.DEBUG_LEVEL == 99
    assert not AppConfig().common.DEBUG_LEVEL == 99

    appconfig.reset_defaults()

    assert appconfig.common.DEBUG_LEVEL == AppConfig().common.DEBUG_LEVEL


def test_appconfig_singleton_reset_autouse_fixture(run_around_tests):
    # autoreset works:

    assert appconfig.common.DEBUG_LEVEL == 98
