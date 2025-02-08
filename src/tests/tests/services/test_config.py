import logging

import pytest

from photobooth.services.configuration import ConfigurationService
from photobooth.services.pluginmanager import PluginManagerService

logger = logging.getLogger(name=None)


@pytest.fixture()
def configuration_service():
    # setup
    cs = ConfigurationService(PluginManagerService())

    yield cs


def test_plugin_config_get_current(configuration_service: ConfigurationService):
    for configurable_plugin_name in configuration_service.list_configurables():
        print(configuration_service.get_current(False, configurable_plugin_name))


def test_plugin_config_get_schema(configuration_service: ConfigurationService):
    for configurable_plugin_name in configuration_service.list_configurables():
        print(configuration_service.get_schema("default", configurable_plugin_name))
