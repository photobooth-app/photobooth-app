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
    for configurables in configuration_service.list_configurables():
        assert configuration_service.get_current(configurables, False)


def test_plugin_config_get_schema(configuration_service: ConfigurationService):
    for configurables in configuration_service.list_configurables():
        assert configuration_service.get_schema(configurables, "default")
