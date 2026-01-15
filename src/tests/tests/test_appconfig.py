"""
Testing virtual camera Backend
"""

import importlib
import logging
import os

import pytest

from photobooth.appconfig import AppConfig, appconfig

logger = logging.getLogger(name=None)


@pytest.fixture()
def run_around_tests():
    # slightly modified fixture to ensure it's executed as expected during tests.
    # modify config, autouse fixture resets in next statement and shall give default values.
    appconfig.common.logging_level = "WARNING"

    yield

    appconfig.reset_defaults()

    assert appconfig.common.logging_level == AppConfig().common.logging_level


def test_appconfig_singleton():
    # modify config:
    appconfig.common.logging_level = "WARNING"
    assert appconfig.common.logging_level == "WARNING"
    assert not AppConfig().common.logging_level == "WARNING"


def test_appconfig_singleton_reset_defaults_manually():
    # modify config:
    appconfig.common.logging_level = "WARNING"
    assert appconfig.common.logging_level == "WARNING"
    assert not AppConfig().common.logging_level == "WARNING"

    appconfig.reset_defaults()

    assert appconfig.common.logging_level == AppConfig().common.logging_level


def test_appconfig_singleton_reset_autouse_fixture(run_around_tests):
    # autoreset works:

    assert appconfig.common.logging_level == "WARNING"


def test_config_references():
    cfg1 = AppConfig()
    cfg2 = cfg1.common
    assert cfg1.common is cfg2


def test_config_references_deep():
    cfg1 = AppConfig()
    cfg2 = cfg1.common.logging_level
    assert cfg1.common.logging_level is cfg2


def test_config_references_deep_changes():
    cfg1 = AppConfig()
    cfg2 = cfg1

    assert cfg1 is cfg2
    cfg2.common.logging_level = "ERROR"
    assert cfg1 is cfg2
    assert cfg1.common.logging_level == "ERROR"
    assert cfg2.common.logging_level == "ERROR"


@pytest.fixture()
def illegalconfig():
    with open(".env.test", "w") as tmpf:
        tmpf.write("common__logging_level=illegalentry")

    yield

    os.remove(".env.test")


def test_config_validation_error(illegalconfig):
    with pytest.raises(SystemExit):
        import photobooth.appconfig

        importlib.reload(photobooth.appconfig)
