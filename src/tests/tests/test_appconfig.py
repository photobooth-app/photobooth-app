"""
Testing virtual camera Backend
"""

import logging

import pytest

from photobooth.appconfig import AppConfig, appconfig
from photobooth.services.config.groups.common import GroupCommon

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


def test_config_retain_references_deep():
    cfg1 = AppConfig()
    cfg2 = cfg1

    assert cfg1 is cfg2

    assert cfg1.common.logging_level == "DEBUG"

    # this is safe when dict is validated before!
    cfg1.__dict__ = AppConfig(common=GroupCommon(logging_level="ERROR")).__dict__

    # cfg1.common.logging_level = "ERROR"
    assert cfg1 is cfg2

    cfg1.common.logging_level = "ERROR"
    cfg2.common.logging_level = "ERROR"

    # assert cfg1.common.logging_level == "WARNING"


def test_config_retain_references_deep_from_dict():
    cfg1 = AppConfig()
    cfg2 = cfg1

    assert cfg1 is cfg2

    assert cfg1.common.logging_level == "DEBUG"

    # this is safe when dict is validated before!
    cfg1.__dict__ = cfg1.model_validate({"common": {"logging_level": "ERROR"}}).__dict__

    assert cfg1 is cfg2

    cfg1.common.logging_level = "ERROR"
    cfg2.common.logging_level = "ERROR"


def test_config_references_deep_change_propagate():
    cfg1 = AppConfig()
    cfg2 = cfg1.common.logging_level

    valid_model = cfg1.model_validate({"common": {"logging_level": "ERROR"}})
    # cfg1.__dict__.update(valid_model)
    cfg1.__dict__ = valid_model.__dict__
    assert cfg1 is not valid_model

    assert cfg1.common.logging_level is not cfg2
    # this is not what we want! we want it to be same!
