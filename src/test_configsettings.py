import platform
import os
import logging
import json
import time
import multiprocessing
from multiprocessing import Process, Value
import pytest
from src import configsettings

logger = logging.getLogger(name=None)

TEST_GROUP = "common"
TEST_KEY = "CAPTURE_CAM_RESOLUTION_HEIGHT"
TEST_KEY_DEFAULT_VALUE = configsettings.ConfigSettings().get_schema()[
    "properties"][TEST_GROUP]["default"][TEST_KEY]
TEST_KEY_TEST_VALUE = TEST_KEY_DEFAULT_VALUE+1

"""
prepare config for testing
several sources of the config: testing here that all sources apply properly:
lowest->highest priority
env
'.env.installer',
'.env.dev',
'.env.prod'
json
init arguments

file '.env' is removed from the list, because behaves different between
windows/linux or python 3.9/3.11:
.env is always loaded on linux/python 3.11 on program start and makes available the stored values.
due to this renaming the files doesn't help because too late.
"""


@pytest.fixture
def tmp_movealloutoftheway():

    filenames = [
        "./config/config.json",
    ]
    filenames.extend(configsettings.ConfigSettings().Config.env_file)

    # rename all files
    for filename in filenames:
        try:
            os.rename(filename, f"{filename.replace('.','_')}")
        except FileNotFoundError:
            # fail silently if file not exists...
            pass

    # yield fixture instead return to allow for cleanup:
    yield

    # return original filenames
    for filename in filenames:
        try:
            os.rename(f"{filename.replace('.', '_')}", filename)
        except FileNotFoundError:
            # fail silently if file not exists...
            pass


@pytest.fixture(params=['.env.installer', '.env.dev', '.env.prod'])
def tmp_envfile(tmp_movealloutoftheway, request):

    with open(request.param, 'w', encoding="utf-8") as env_file:
        env_file.write(
            f"{TEST_GROUP}__{TEST_KEY}='{TEST_KEY_TEST_VALUE}'")

    # yield fixture instead return to allow for cleanup:
    yield

    # cleanup
    os.remove(request.param)


def test_configsettings_issingleton():
    from src.configsettings import settings
    assert settings == configsettings.ConfigSettings()
    assert settings is configsettings.ConfigSettings()
    assert configsettings.ConfigSettings() == configsettings.ConfigSettings()
    assert configsettings.ConfigSettings() is configsettings.ConfigSettings()
    configsettings.ConfigSettings()
    settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT = 123
    assert settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT == 123


def test_comparesettings_vs_configsettings():
    from src.configsettings import settings
    assert settings == configsettings.ConfigSettings()


def test_defaultsetting(tmp_movealloutoftheway):
    assert configsettings.ConfigSettings(
    ).common.CAPTURE_CAM_RESOLUTION_HEIGHT == TEST_KEY_DEFAULT_VALUE


def test_envfiles(tmp_envfile):
    assert configsettings.ConfigSettings(
    ).common.CAPTURE_CAM_RESOLUTION_HEIGHT == TEST_KEY_TEST_VALUE


def test_init_updated_settings():
    updatedSettings = configsettings.ConfigSettings(
        common={'CAPTURE_CAM_RESOLUTION_HEIGHT': TEST_KEY_TEST_VALUE})
    assert updatedSettings.common.CAPTURE_CAM_RESOLUTION_HEIGHT == TEST_KEY_TEST_VALUE


def test_updated_settings_in_singleton_available():
    from src.configsettings import settings

    settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT = TEST_KEY_TEST_VALUE
    assert settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT == TEST_KEY_TEST_VALUE

    assert settings is configsettings.ConfigSettings()


def _separate_process_no_settings_passed_fun(checkValue: Value):
    from src.configsettings import settings
    checkValue.value = settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT


def _separate_process_settings_passed_fun(checkValue: Value,
                                          settings: configsettings.ConfigSettings):
    checkValue.value = settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT


def test_settings_available_in_separate_spawned_process():
    from src.configsettings import settings
    ORIGINAL_TEST_KEY_VALUE = settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT

    # now change the value
    settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT = TEST_KEY_TEST_VALUE
    assert settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT == TEST_KEY_TEST_VALUE

    multiprocessing.set_start_method('spawn', force=True)

    check_value1 = Value("i", 0)
    _p1 = Process(target=_separate_process_no_settings_passed_fun,
                  args=(check_value1,), daemon=True)
    _p1.start()

    # wait long enough, that the process has started actually
    time.sleep(2)
    # can show that separate processes to not receive the changed settings!
    # complete separate memory. need to share settings explicitly if changes need to be shared (for tests)
    assert check_value1.value == ORIGINAL_TEST_KEY_VALUE
    logger.warning(
        "in process the value is still the original value, changed setting not reflected.")

    _p1.terminate()
    _p1.join(1)
    _p1.close()

    check_value2 = Value("i", 0)
    _p2 = Process(target=_separate_process_settings_passed_fun,
                  args=(check_value2, settings), daemon=True)
    _p2.start()
    time.sleep(2)

    assert check_value2.value == TEST_KEY_TEST_VALUE
    logger.warning(
        "in process the value changed, this is good. "
        "so passing settings to processes is necessary if start_method is 'spawn'"
    )

    _p2.terminate()
    _p2.join(1)
    _p2.close()


def test_settings_available_in_separate_forked_process():
    if not platform.system() == "Linux":
        pytest.skip(
            "forked processes only avail on linux is linux only platform, skipping test")

    from src.configsettings import settings
    ORIGINAL_TEST_KEY_VALUE = settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT

    # now change the value
    settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT = TEST_KEY_TEST_VALUE
    assert settings.common.CAPTURE_CAM_RESOLUTION_HEIGHT == TEST_KEY_TEST_VALUE

    multiprocessing.set_start_method('fork', force=True)

    check_value3 = Value("i", 0)
    _p3 = Process(target=_separate_process_no_settings_passed_fun,
                  args=(check_value3,), daemon=True)
    _p3.start()
    time.sleep(2)

    assert check_value3.value == TEST_KEY_TEST_VALUE
    logger.warning(
        "in process the value changed, this is good. "
        "so passing settings to processes is NOT necessary if start_method is 'fork'"
    )

    _p3.terminate()
    _p3.join(2)
    _p3.close()


def test_PersistSettings(tmp_movealloutoftheway):
    updated_settings = configsettings.ConfigSettings(
        common={'CAPTURE_CAM_RESOLUTION_HEIGHT': TEST_KEY_TEST_VALUE})

    # creates config/config.json
    updated_settings.persist()

    with open('./config/config.json', "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data[TEST_GROUP][TEST_KEY] == TEST_KEY_TEST_VALUE

    # remove test file again
    os.remove('./config/config.json')
