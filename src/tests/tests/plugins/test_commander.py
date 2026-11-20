import logging
import subprocess
import time
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import requests
from pydantic import HttpUrl
from statemachine import Event, State

from photobooth.appconfig import appconfig
from photobooth.database.models import Mediaitem
from photobooth.plugins.commander.commander import Commander
from photobooth.plugins.commander.config import CommanderConfig
from photobooth.plugins.commander.models import HttpRequestParameters, TaskCommand, TaskHttpRequest
from photobooth.services.acquisition import AcquisitionService
from photobooth.services.processing import PluginEventHooks, ProcessingMachine
from photobooth.services.processor.image import JobModelImage

logger = logging.getLogger(name=None)


def make_mediaitem(filepath: Path) -> Mediaitem:
    return Mediaitem(
        id=uuid4(),
        media_type="image",
        processed=filepath,
        pipeline_config={},
        show_in_gallery=True,
    )


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
            TaskCommand(command="echo this echoed on event {event}!", filter_mediaitem_types=["video"]),
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
        commander_plugin.sm_on_enter_state(State(), ProcessingMachine.counting, Event(), "image")
        mock_run_task.assert_called_once_with("counting", "image", None)

    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.sm_on_enter_state(State(), ProcessingMachine.finished, Event(), "image")
        mock_run_task.assert_called_once_with("finished", "image", None)

    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.sm_on_enter_state(State(), ProcessingMachine.capture, Event(), "image")
        mock_run_task.assert_called_once_with("capture", "image", None)


def test_sm_on_exit_state(commander_plugin: Commander):
    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.sm_on_exit_state(ProcessingMachine.capture, State(), Event(), "image")
        mock_run_task.assert_called_once_with("captured", "image", None)


def test_processing_hook_passes_present_mediaitem(tmp_path: Path):
    mediaitem = make_mediaitem(tmp_path / "photo.jpg")
    model = JobModelImage(appconfig.actions.image[0], AcquisitionService())
    model._present_mediaitem_id = mediaitem.id
    model._result_mediaitems = [mediaitem]

    with patch("photobooth.services.processing.pluggy_pm.hook.sm_on_enter_state") as mock_hook:
        PluginEventHooks().on_enter_state(State(), ProcessingMachine.finished, Event(), model)

    assert mock_hook.call_args.kwargs["mediaitem"] is mediaitem


@pytest.mark.parametrize("with_mediaitem", [True, False])
def test_invoke_command_formats_filepath(commander_plugin: Commander, tmp_path: Path, with_mediaitem: bool):
    mediaitem = make_mediaitem(tmp_path / "photo.jpg") if with_mediaitem else None
    filepath = str(mediaitem.processed.resolve()) if mediaitem else ""
    task = TaskCommand(command="print {filepath}", wait_until_completed=True)

    with patch.object(subprocess, "run") as mock_subprocess_run:
        commander_plugin.invoke_command(task, "finished", "image", mediaitem)

    assert mock_subprocess_run.call_args.kwargs["args"] == f"print {filepath}"


@pytest.mark.parametrize("with_mediaitem", [True, False])
def test_invoke_http_formats_filepath(commander_plugin: Commander, tmp_path: Path, with_mediaitem: bool):
    mediaitem = make_mediaitem(tmp_path / "photo.jpg") if with_mediaitem else None
    filepath = str(mediaitem.processed.resolve()) if mediaitem else ""
    task = TaskHttpRequest(
        url=HttpUrl("http://127.0.0.1/"),
        parameter=[HttpRequestParameters(key="filepath", value="{filepath}")],
        wait_until_completed=True,
    )

    with patch.object(requests, "request") as mock_requests_request:
        commander_plugin.invoke_httprequest(task, "finished", "image", mediaitem)

    assert mock_requests_request.call_args.kwargs["params"] == {"filepath": filepath}


def test_run_task(commander_plugin: Commander):
    with patch.object(commander_plugin, "invoke_command") as mock_invoke_command:
        with patch.object(commander_plugin, "invoke_httprequest") as mock_invoke_httprequest:
            commander_plugin.run_task("finished")

            assert mock_invoke_command.call_count == len([cmd for cmd in commander_plugin._config.tasks_commands if cmd.enabled is True])
            assert mock_invoke_httprequest.call_count == len([req for req in commander_plugin._config.tasks_httprequests if req.enabled is True])


def test_run_task_filtered(commander_plugin: Commander):
    with patch.object(commander_plugin, "invoke_command") as mock_invoke_command:
        with patch.object(commander_plugin, "invoke_httprequest") as mock_invoke_httprequest:
            commander_plugin.run_task("finished", "video")

            assert mock_invoke_command.call_count == len(
                [
                    cmd
                    for cmd in commander_plugin._config.tasks_commands
                    if cmd.enabled is True and (not cmd.filter_mediaitem_types or "video" in cmd.filter_mediaitem_types)
                ]
            )
            assert mock_invoke_httprequest.call_count == len(
                [
                    req
                    for req in commander_plugin._config.tasks_httprequests
                    if req.enabled is True and (not req.filter_mediaitem_types or "video" in req.filter_mediaitem_types)
                ]
            )


def test_acq_before_get_still(commander_plugin: Commander):
    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.acq_before_get_still()
        mock_run_task.assert_called_once_with("capture_still")


def test_acq_before_get_multicam(commander_plugin: Commander):
    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.acq_before_get_multicam()
        mock_run_task.assert_called_once_with("capture_multicam")


def test_acq_before_get_video(commander_plugin: Commander):
    with patch.object(commander_plugin, "run_task") as mock_run_task:
        commander_plugin.acq_before_get_video()
        mock_run_task.assert_called_once_with("capture_video")


def test_invoke_command(commander_plugin: Commander):
    with patch.object(subprocess, "run") as mock_subprocess_run:
        for cmd in commander_plugin._config.tasks_commands:
            commander_plugin.invoke_command(cmd, "finished", None)

        time.sleep(0.4)  # wait until thread has finished actually even on not waiting to make mock count

        assert mock_subprocess_run.call_count == len(commander_plugin._config.tasks_commands)


def test_invoke_command_error(commander_plugin: Commander):
    with patch.object(subprocess, "run", side_effect=RuntimeError("mocked,swallowed")) as mock_subprocess_run:
        commander_plugin.invoke_command(TaskCommand(command="echo this echoed on event {event}!", wait_until_completed=True), "finished", None)
        mock_subprocess_run.assert_called()

    with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired("mocked,swallowed", 6)) as mock_subprocess_run:
        commander_plugin.invoke_command(TaskCommand(command="echo this echoed on event {event}!", wait_until_completed=True), "finished", None)
        mock_subprocess_run.assert_called()

    with patch.object(subprocess, "run", side_effect=subprocess.CalledProcessError(1, "mocked,swallowed")) as mock_subprocess_run:
        commander_plugin.invoke_command(TaskCommand(command="echo this echoed on event {event}!", wait_until_completed=True), "finished", None)
        mock_subprocess_run.assert_called()


def test_invoke_http(commander_plugin: Commander):
    with patch.object(requests, "request") as mock_requests_request:
        for req in commander_plugin._config.tasks_httprequests:
            commander_plugin.invoke_httprequest(req, "finished", None)

        time.sleep(0.4)  # wait until thread has finished actually even on not waiting to make mock count

        assert mock_requests_request.call_count == len(commander_plugin._config.tasks_httprequests)


def test_invoke_http_error(commander_plugin: Commander):
    with patch.object(requests, "request", side_effect=RuntimeError("mocked,swallowed")) as mock_req:
        commander_plugin.invoke_httprequest(TaskHttpRequest(url=HttpUrl("http://127.0.0.1/"), wait_until_completed=True), "finished", None)
        mock_req.assert_called()

    fake_response = requests.Response()
    fake_response.status_code = 500
    with patch.object(requests, "request", side_effect=requests.exceptions.HTTPError(response=fake_response)) as mock_req:
        commander_plugin.invoke_httprequest(TaskHttpRequest(url=HttpUrl("http://127.0.0.1/"), wait_until_completed=True), "finished", None)
        mock_req.assert_called()

    with patch.object(requests, "request", side_effect=requests.exceptions.RequestException()) as mock_req:
        commander_plugin.invoke_httprequest(TaskHttpRequest(url=HttpUrl("http://127.0.0.1/"), wait_until_completed=True), "finished", None)
        mock_req.assert_called()
