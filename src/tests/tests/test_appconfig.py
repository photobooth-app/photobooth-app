"""
Testing virtual camera Backend
"""

import importlib
import logging
import os
from pathlib import Path

import pytest

from photobooth.appconfig import AppConfig, appconfig
from photobooth.services.config.groups.actions import CollageProcessing, SingleImageProcessing
from photobooth.services.config.models.models import ImageElementConfig, TextElementConfig

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


def test_migrate_legacy_texts_single_image():
    config = SingleImageProcessing.model_validate({"texts_enable": True, "texts": [{"text": "legacy", "rotate": 5}]})

    assert config.elements_enable is True
    assert len(config.elements) == 1
    assert isinstance(config.elements[0], TextElementConfig)
    assert config.elements[0].text == "legacy"
    assert config.elements[0].rotate == 5
    assert "texts" not in config.model_dump()


def test_migrate_legacy_texts_collage():
    config = CollageProcessing.model_validate({"merge_definition": [], "canvas_texts_enable": True, "canvas_texts": [{"text": "legacy"}]})

    assert config.canvas_elements_enable is True
    assert isinstance(config.canvas_elements[0], TextElementConfig)
    assert config.canvas_elements[0].text == "legacy"


def test_migrate_legacy_texts_new_key_wins():
    config = SingleImageProcessing.model_validate({"texts": [{"text": "old"}], "elements": [{"type": "text", "text": "new"}]})

    assert len(config.elements) == 1
    assert isinstance(config.elements[0], TextElementConfig)
    assert config.elements[0].text == "new"


def test_canvas_elements_mixed_and_untyped():
    font = "userdata/demoassets/fonts/Roboto-Bold.ttf"
    logo = "userdata/demoassets/frames/frame_image_photobooth-app.png"
    config = SingleImageProcessing.model_validate({"elements": [{"text": "untyped", "font": font}, {"type": "image", "image": logo}]})

    assert isinstance(config.elements[0], TextElementConfig)
    assert isinstance(config.elements[1], ImageElementConfig)

    # roundtrip as stored in config file / database
    assert SingleImageProcessing.model_validate(config.model_dump(mode="json")) == config


def test_config_migrate_legacy_v9_img_frame():
    config = SingleImageProcessing.model_validate(
        {"img_frame": {"enable": True, "image": "userdata/demoassets/frames/frame_image_photobooth-app.png", "mirror_effect": True}}
    )

    assert config.img_frame_enable is True
    assert config.img_frame_file == Path("userdata/demoassets/frames/frame_image_photobooth-app.png")
    assert config.img_frame_preview_mirror is True
    assert config.img_frame_preview_enable is True
