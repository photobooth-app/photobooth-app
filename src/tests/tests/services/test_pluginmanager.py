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
