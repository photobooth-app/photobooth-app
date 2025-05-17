import logging

import pytest

from photobooth.services.pluginmanager import PluginManagerService

logger = logging.getLogger(name=None)


@pytest.fixture()
def pluginmanager_service():
    # setup
    cs = PluginManagerService()

    yield cs


def test_list_plugins(pluginmanager_service: PluginManagerService):
    assert pluginmanager_service.list_plugins()


def test_get_plugin_stats(pluginmanager_service: PluginManagerService):
    logger.warning(pluginmanager_service.get_plugins_stats())
    assert False
