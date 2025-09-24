import logging
import subprocess
import threading
import time

import niquests
from statemachine import Event, State

from ...database.models import MediaitemTypes
from ...services.processor.machine.processingmachine import ProcessingMachine
from .. import hookimpl
from ..base_plugin import BasePlugin
from .config import CommanderConfig
from .models import TaskCommand, TaskHttpRequest, eventHooks, requestMethods

logger = logging.getLogger(__name__)


class ThreadCommand(threading.Thread):
    def __init__(self, task: TaskCommand, event: eventHooks, mediaitem_type: MediaitemTypes | None):
        super().__init__(daemon=True)
        fmt = {"event": event, "mediaitem_type": mediaitem_type.value if mediaitem_type else None}
        self.command = str(task.command).format(**fmt)
        self.delay_before = task.delay_before
        self.timeout = task.timeout

    def run(self):
        logger.info(f"run command '{self.command}' with {self.delay_before}s delay")

        time.sleep(self.delay_before)

        try:
            completed_process = subprocess.run(
                args=self.command,
                timeout=self.timeout,
                check=True,
                capture_output=True,
                shell=True,
            )
        except subprocess.TimeoutExpired as exc:
            logger.warning(exc)
            logger.warning(f"the command '{self.command}' timed out after {exc.timeout}s")
        except subprocess.CalledProcessError as exc:
            logger.warning(exc)
            logger.warning(f"the command '{self.command}' was executed but returned an error code {exc.returncode}")
        except Exception as exc:
            logger.error(f"error executing command, error: {exc}")
        else:
            logger.debug(completed_process)
            logger.info(f"command {self.command} finished successfully")


class ThreadUrl(threading.Thread):
    def __init__(self, task: TaskHttpRequest, event: eventHooks, mediaitem_type: MediaitemTypes | None):
        super().__init__(daemon=True)
        self.url = str(task.url)
        self.delay_before = task.delay_before
        self.timeout = task.timeout
        self.body_parameters_as_json = task.body_parameters_as_json
        fmt = {"event": event, "mediaitem_type": mediaitem_type.value if mediaitem_type else None}
        self.query_params: dict[str, str] = {param.key: str(param.value).format(**fmt) for param in task.parameter if param.where == "query"}
        self.body_params: dict[str, str] = {param.key: str(param.value).format(**fmt) for param in task.parameter if param.where == "body"}
        self.method: requestMethods = task.method
        self.event = event

    def run(self):
        logger.info(f"run http request '{self.url}' with {self.delay_before}s delay")

        time.sleep(self.delay_before)

        req_data = req_json = None
        if self.body_parameters_as_json is True:
            req_json = self.body_params
        else:
            req_data = self.body_params

        try:
            r = niquests.request(
                method=self.method,
                url=self.url,
                params=self.query_params,
                timeout=self.timeout,
                data=req_data,
                json=req_json,
            )

            r.raise_for_status()

        except niquests.exceptions.HTTPError as exc:
            logger.error(f"http request sent but remote returned error code {exc.response.status_code if exc.response else 'None'}, error {exc}")
        except niquests.exceptions.RequestException as exc:  # catches .Timeout | .TooManyRedirects | .ConnectionError
            logger.error(f"error sending http request, error {exc}")
        except Exception as exc:
            logger.error(f"unknown error in http request, error {exc}")
        else:
            r_text = r.text[:100] if r.text else "(None)"
            r_text_truncated = len(r.text) > 100 if r.text else False
            logger.debug(
                f"response code '{r.status_code}', text '{r_text}' "
                f"{'[trunc to 100 chars for log msg]' if r_text_truncated else ''}, within {round(r.elapsed.total_seconds(), 1)}s"
            )
            logger.info(f"request to {self.url} finished successfully")


class Commander(BasePlugin[CommanderConfig]):
    def __init__(self):
        super().__init__()

        self._config: CommanderConfig = CommanderConfig()

    ## service hooks
    @hookimpl
    def init(self):
        self.run_task("init")

    @hookimpl
    def start(self):
        self.run_task("start")

    @hookimpl
    def stop(self):
        self.run_task("stop")

    ## state machine processing hooks
    @hookimpl
    def sm_on_enter_state(self, source: State, target: State, event: Event, mediaitem_type: MediaitemTypes):
        if target == ProcessingMachine.counting:
            self.run_task("counting", mediaitem_type)
        elif target == ProcessingMachine.finished:
            self.run_task("finished", mediaitem_type)
        elif target == ProcessingMachine.capture:
            self.run_task("capture", mediaitem_type)

    @hookimpl
    def sm_on_exit_state(self, source: State, target: State, event: Event, mediaitem_type: MediaitemTypes):
        if source == ProcessingMachine.capture:
            self.run_task("captured", mediaitem_type)

    ## acquisition service hooks
    @hookimpl
    def acq_before_get_still(self):
        self.run_task("capture_still")

    @hookimpl
    def acq_before_get_multicam(self):
        self.run_task("capture_multicam")

    @hookimpl
    def acq_before_get_video(self):
        self.run_task("capture_video")

    def invoke_command(self, task_to_run: TaskCommand, event: eventHooks, mediaitem_type: MediaitemTypes | None):
        t = ThreadCommand(task_to_run, event, mediaitem_type)
        t.start()

        if task_to_run.wait_until_completed:
            t.join()

    def invoke_httprequest(self, task_to_run: TaskHttpRequest, event: eventHooks, mediaitem_type: MediaitemTypes | None):
        t = ThreadUrl(task_to_run, event, mediaitem_type)
        t.start()

        if task_to_run.wait_until_completed:
            t.join()

    def run_task(self, event: eventHooks, mediaitem_type: MediaitemTypes | None = None):
        if not self._config.enable_tasks_processing:
            # ignore any request if not enabled overall processing...
            return

        tasks_to_run = [task for task in (self._config.tasks_commands + self._config.tasks_httprequests) if (event in task.event and task.enabled)]

        # filter out some tasks if mediaitem_type is given for states
        if mediaitem_type is not None:
            tasks_to_run = [task for task in tasks_to_run if (not task.filter_mediaitem_types or mediaitem_type in task.filter_mediaitem_types)]

        logger.info(f"{len(tasks_to_run)} tasks to run for {event=}: {tasks_to_run}")

        for task_to_run in tasks_to_run:
            if isinstance(task_to_run, TaskCommand):
                self.invoke_command(task_to_run, event, mediaitem_type)
            elif isinstance(task_to_run, TaskHttpRequest):
                self.invoke_httprequest(task_to_run, event, mediaitem_type)
            # else cannot happen because of pydantic validation before...
