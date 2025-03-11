import logging
import subprocess
import time
from unittest.mock import patch

import pytest
import requests
from pydantic import HttpUrl
from statemachine import Event, State

from photobooth.plugins.commander.commander import Commander
from photobooth.plugins.commander.config import CommanderConfig
from photobooth.plugins.commander.models import HttpRequestParameters, TaskCommand, TaskHttpRequest
from photobooth.services.processing import ProcessingMachine

logger = logging.getLogger(name=None)


@pytest.fixture()
def commander_plugin():
    # setup
    cmdr = Commander()

    cmdr._config = CommanderConfig(
        enable_tasks_processing=True,
        tasks_httprequests=[
            TaskHttpRequest(
                url=HttpUrl("http://127.0.0.1/"),
                parameter=[HttpRequestParameters(key="event_key", value="{event}")],
            ),
            TaskHttpRequest(
                url=HttpUrl("http://127.0.0.1/"), parameter=[HttpRequestParameters(key="event_key", value="{event}")], wait_until_completed=True
            ),
            TaskHttpRequest(
                url=HttpUrl("http://127.0.0.1/"),
                parameter=[HttpRequestParameters(key="event_key", value="{event}", where="body")],
            ),
            TaskHttpRequest(
                url=HttpUrl("http://127.0.0.1/"),
                parameter=[HttpRequestParameters(key="event_key", value="{event}", where="body")],
                body_parameters_as_json=False,
            ),
            TaskHttpRequest(enabled=False, url=HttpUrl("http://127.0.0.1/"), wait_until_completed=True),
        ],
        tasks_commands=[
            TaskCommand(command="echo this echoed on event {event}!"),
            TaskCommand(command="echo this echoed on event {event}!", wait_until_completed=True),
        ],
    )

    yield cmdr


def test_init(commander_plugin: Commander):
    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.init()
        mock_run_task.assert_called_once_with("init")


def test_start(commander_plugin: Commander):
    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.start()
        mock_run_task.assert_called_once_with("start")


def test_stop(commander_plugin: Commander):
    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.stop()
        mock_run_task.assert_called_once_with("stop")


def test_sm_on_enter_state(commander_plugin: Commander):
    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.sm_on_enter_state(State(), ProcessingMachine.counting, Event())
        mock_run_task.assert_called_once_with("counting")

    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.sm_on_enter_state(State(), ProcessingMachine.finished, Event())
        mock_run_task.assert_called_once_with("finished")

    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.sm_on_enter_state(State(), ProcessingMachine.record, Event())
        mock_run_task.assert_called_once_with("record")


def test_sm_on_exit_state(commander_plugin: Commander):
    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.sm_on_exit_state(ProcessingMachine.capture, State(), Event())
        mock_run_task.assert_called_once_with("captured")

    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.sm_on_exit_state(ProcessingMachine.record, State(), Event())
        mock_run_task.assert_called_once_with("captured")


def test_run_task(commander_plugin: Commander):
    with patch.object(commander_plugin, "invoke_command") as mock_invoke_command:
        with patch.object(commander_plugin, "invoke_httprequest") as mock_invoke_httprequest:
            commander_plugin.run_task("finished")

            assert mock_invoke_command.call_count == len([cmd for cmd in commander_plugin._config.tasks_commands if cmd.enabled is True])
            assert mock_invoke_httprequest.call_count == len([req for req in commander_plugin._config.tasks_httprequests if req.enabled is True])


def test_invoke_command(commander_plugin: Commander):
    with patch.object(subprocess, "run") as mock_subprocess_run:
        for cmd in commander_plugin._config.tasks_commands:
            commander_plugin.invoke_command(cmd, "finished")

        time.sleep(0.4)  # wait until thread has finished actually even on not waiting to make mock count

        assert mock_subprocess_run.call_count == len(commander_plugin._config.tasks_commands)


def test_invoke_command_error(commander_plugin: Commander):
    with patch.object(subprocess, "run", side_effect=RuntimeError("mocked,swallowed")) as mock_subprocess_run:
        commander_plugin.invoke_command(TaskCommand(command="echo this echoed on event {event}!", wait_until_completed=True), "finished")
        mock_subprocess_run.assert_called()

    with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired("mocked,swallowed", 6)) as mock_subprocess_run:
        commander_plugin.invoke_command(TaskCommand(command="echo this echoed on event {event}!", wait_until_completed=True), "finished")
        mock_subprocess_run.assert_called()

    with patch.object(subprocess, "run", side_effect=subprocess.CalledProcessError(1, "mocked,swallowed")) as mock_subprocess_run:
        commander_plugin.invoke_command(TaskCommand(command="echo this echoed on event {event}!", wait_until_completed=True), "finished")
        mock_subprocess_run.assert_called()


def test_invoke_http(commander_plugin: Commander):
    with patch.object(requests, "request") as mock_requests_request:
        for req in commander_plugin._config.tasks_httprequests:
            commander_plugin.invoke_httprequest(req, "finished")

        time.sleep(0.4)  # wait until thread has finished actually even on not waiting to make mock count

        assert mock_requests_request.call_count == len(commander_plugin._config.tasks_httprequests)


def test_invoke_http_error(commander_plugin: Commander):
    with patch.object(requests, "request", side_effect=RuntimeError("mocked,swallowed")) as mock_req:
        commander_plugin.invoke_httprequest(TaskHttpRequest(url=HttpUrl("http://127.0.0.1/"), wait_until_completed=True), "finished")
        mock_req.assert_called()

    fake_response = requests.Response()
    fake_response.status_code = 500
    with patch.object(requests, "request", side_effect=requests.exceptions.HTTPError(response=fake_response)) as mock_req:
        commander_plugin.invoke_httprequest(TaskHttpRequest(url=HttpUrl("http://127.0.0.1/"), wait_until_completed=True), "finished")
        mock_req.assert_called()

    with patch.object(requests, "request", side_effect=requests.exceptions.RequestException()) as mock_req:
        commander_plugin.invoke_httprequest(TaskHttpRequest(url=HttpUrl("http://127.0.0.1/"), wait_until_completed=True), "finished")
        mock_req.assert_called()
