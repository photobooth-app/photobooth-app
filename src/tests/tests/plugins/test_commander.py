import logging

import pytest
from statemachine import Event, State

from photobooth.plugins.commander.commander import Commander
from photobooth.services.processing import ProcessingMachine

logger = logging.getLogger(name=None)


@pytest.fixture()
def commander_plugin():
    # setup
    cmdr = Commander()
    cmdr._config.enable_tasks_processing = True

    yield cmdr


def test_start(commander_plugin: Commander):
    commander_plugin.start()


def test_stop(commander_plugin: Commander):
    commander_plugin.stop()


def test_sm_on_enter_state(commander_plugin: Commander):
    commander_plugin.sm_on_enter_state(State(), ProcessingMachine.counting, Event())
    commander_plugin.sm_on_enter_state(State(), ProcessingMachine.finished, Event())
    commander_plugin.sm_on_enter_state(State(), ProcessingMachine.record, Event())


def test_sm_on_exit_state(commander_plugin: Commander):
    commander_plugin.sm_on_exit_state(ProcessingMachine.capture, State(), Event())
    commander_plugin.sm_on_exit_state(ProcessingMachine.record, State(), Event())
