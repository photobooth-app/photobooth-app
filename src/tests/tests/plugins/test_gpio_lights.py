import logging
from collections.abc import Generator
from typing import cast
from unittest.mock import patch

import pytest
from gpiozero.pins.mock import MockPin

from photobooth.container import Container, container
from photobooth.plugins.gpio_lights.gpio_lights import GpioLights

from ..util import get_impl_func_for_plugin

logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Generator[Container, None, None]:
    gpio_lights_plugin = cast(GpioLights, container.pluginmanager_service.get_plugin("photobooth.plugins.gpio_lights.gpio_lights"))
    gpio_lights_plugin._config.plugin_enabled = True

    container.start()
    yield container
    container.stop()


def test_hooks_integration(_container: Container):
    gpio_lights_plugin = cast(GpioLights, _container.pluginmanager_service.get_plugin("photobooth.plugins.gpio_lights.gpio_lights"))
    assert gpio_lights_plugin is not None

    mock_hookimpl = get_impl_func_for_plugin(gpio_lights_plugin, _container.pluginmanager_service.pm.hook.sm_on_enter_state)
    with patch.object(mock_hookimpl, "function") as mock_hook:
        _container.processing_service.trigger_action("image", 0)
        _container.processing_service.wait_until_job_finished()

        mock_hook.assert_called()


def test_light_switched_during_process(_container: Container):
    gpio_lights_plugin = cast(GpioLights, _container.pluginmanager_service.get_plugin("photobooth.plugins.gpio_lights.gpio_lights"))

    assert gpio_lights_plugin.light_out
    pin = cast(MockPin, gpio_lights_plugin.light_out.pin)
    pin.clear_states()

    _container.processing_service.trigger_action("image", 0)
    _container.processing_service.wait_until_job_finished()

    # could use also pin.assert_states but strict is false and so it would not fail if more states are present.
    for actual, expected in zip(pin.states, [True, False, True], strict=True):
        assert actual.state == expected


def test_light_switched_during_process_turn_off_after_capture(_container: Container):
    gpio_lights_plugin = cast(GpioLights, _container.pluginmanager_service.get_plugin("photobooth.plugins.gpio_lights.gpio_lights"))
    gpio_lights_plugin._config.gpio_light_off_after_capture = True

    assert gpio_lights_plugin.light_out
    pin = cast(MockPin, gpio_lights_plugin.light_out.pin)
    pin.clear_states()

    _container.processing_service.trigger_action("collage", 0)
    _container.processing_service.wait_until_job_finished()

    # could use also pin.assert_states but strict is false and so it would not fail if more states are present.
    for actual, expected in zip(pin.states, [True, False, True, False, True], strict=True):
        assert actual.state == expected

    gpio_lights_plugin._config.gpio_light_off_after_capture = False
    pin.clear_states()

    _container.processing_service.trigger_action("collage", 0)
    _container.processing_service.wait_until_job_finished()

    # could use also pin.assert_states but strict is false and so it would not fail if more states are present.
    for actual, expected in zip(pin.states, [True, False, True], strict=True):
        assert actual.state == expected
