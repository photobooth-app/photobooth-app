import logging
from unittest.mock import patch

from photobooth.container import container

from ..util import get_impl_func_for_plugin

logger = logging.getLogger(name=None)


def test_hooks_integration_start_stop_if_hook_implemented():
    plugins = container.pluginmanager_service.pm.get_plugins()
    number_should_start_calls = 0
    number_should_stop_calls = 0
    number_actual_start_calls = 0
    number_actual_stop_calls = 0

    for plugin in plugins:
        if not getattr(plugin, "start", None):
            continue
        number_should_start_calls += 1

        mock_hookimpl = get_impl_func_for_plugin(plugin, container.pluginmanager_service.pm.hook.start)
        with patch.object(mock_hookimpl, "function") as mock_hook:
            container.start()

            mock_hook.assert_called()
            number_actual_start_calls += 1

        if not getattr(plugin, "stop", None):
            continue

        number_should_stop_calls += 1
        mock_hookimpl = get_impl_func_for_plugin(plugin, container.pluginmanager_service.pm.hook.stop)
        with patch.object(mock_hookimpl, "function") as mock_hook:
            container.stop()

            mock_hook.assert_called()
            number_actual_stop_calls += 1

    assert number_actual_start_calls == number_should_start_calls
    assert number_actual_stop_calls == number_should_stop_calls
