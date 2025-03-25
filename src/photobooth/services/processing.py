import logging
from queue import Empty, Queue
from threading import Thread
from typing import Literal
from uuid import UUID

from statemachine import Event, State

from ..appconfig import appconfig
from ..plugins import pm as pluggy_pm
from ..utils.exceptions import ProcessMachineOccupiedError
from .aquisition import AquisitionService
from .base import BaseService
from .collection import MediacollectionService
from .config.groups.actions import MultiImageJobControl
from .information import InformationService
from .processor.animation import JobModelAnimation
from .processor.base import Capture
from .processor.collage import JobModelCollage
from .processor.image import JobModelImage
from .processor.machine.processingmachine import ProcessingMachine
from .processor.multicamera import JobModelMulticamera
from .processor.video import JobModelVideo
from .sse import sse_service
from .sse.sse_ import SseEventFrontendNotification, SseEventProcessStateinfo

logger = logging.getLogger(__name__)


ActionType = Literal["image", "collage", "animation", "video", "multicamera"]


class MachineChangeListenter:
    def on_enter_state(self, source: State, target: State, event: Event):
        logger.info(f"Entering {target} by {event}-event, leaving {source}")


class DbListenter:
    def __init__(self, mediacollection_service: MediacollectionService):
        self._mediacollection_service = mediacollection_service

    def on_exit_state(self, source: State, target: State, model: JobModelImage | JobModelCollage):
        if source.id == ProcessingMachine.completed.id:
            if model._result_mediaitems:
                logger.info(f"add {len(model._result_mediaitems)} results to db")

                for items in model._result_mediaitems:
                    self._mediacollection_service.add_item(items)  # and to the db.


class PluginEventHooks:
    def __init__(self):
        # https://python-statemachine.readthedocs.io/en/latest/actions.html#ordering
        pass

    def before_transition(self, source: State, target: State, event: Event):
        pluggy_pm.hook.sm_before_transition(source=source, target=target, event=event)

    def on_exit_state(self, source: State, target: State, event: Event):
        pluggy_pm.hook.sm_on_exit_state(source=source, target=target, event=event)

    def on_transition(self, source: State, target: State, event: Event):
        pluggy_pm.hook.sm_on_transition(source=source, target=target, event=event)

    def on_enter_state(self, source: State, target: State, event: Event):
        pluggy_pm.hook.sm_on_enter_state(source=source, target=target, event=event)

    def after_transition(self, source: State, target: State, event: Event):
        pluggy_pm.hook.sm_after_transition(source=source, target=target, event=event)


class FrontendNotifierEventHooks:
    emit_before_transition_to_target = (ProcessingMachine.completed,)  # emit before processing to allow UI show processing on target=completed

    def before_transition(self, source: State, target: State, model):
        if target in self.emit_before_transition_to_target:
            logger.info(f"send frontend notification {source=} {target=}")
            sse_service.dispatch_event(SseEventProcessStateinfo(source=source, target=target, jobmodel=model))

    def after_transition(self, source: State, target: State, model):
        if target not in self.emit_before_transition_to_target:
            logger.info(f"send frontend notification {source=} {target=}")
            sse_service.dispatch_event(SseEventProcessStateinfo(source=source, target=target, jobmodel=model))


class ProcessingService(BaseService):
    def __init__(
        self,
        aquisition_service: AquisitionService,
        mediacollection_service: MediacollectionService,
        information_service: InformationService,
    ):
        super().__init__()

        self._aquisition_service: AquisitionService = aquisition_service
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._information_service: InformationService = information_service

        # objects
        self._workflow_jobmodel: JobModelImage | JobModelCollage | JobModelAnimation | JobModelVideo | JobModelMulticamera | None = None
        self._process_thread: Thread | None = None

        # start with clear queue
        self._external_cmd_queue: Queue[str] = Queue[str](maxsize=1)

    def _check_occupied(self):
        if self._workflow_jobmodel is not None:
            sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="info",
                    message="There is already a job running. Please wait until it finished.",
                    caption="Job in process ⌛",
                )
            )
            raise ProcessMachineOccupiedError("bad request, only one request at a time!")

    def _process_fun(self):
        assert self._workflow_jobmodel
        assert self._workflow_jobmodel._status_sm.current_state == ProcessingMachine.initial_state

        try:
            logger.info("starting job")

            while not self._workflow_jobmodel._status_sm.current_state == ProcessingMachine.finished:
                if self._workflow_jobmodel._status_sm.current_state == ProcessingMachine.approval:
                    assert isinstance(self._workflow_jobmodel._configuration_set.jobcontrol, MultiImageJobControl)

                    timeout = self._workflow_jobmodel._configuration_set.jobcontrol.approve_autoconfirm_timeout
                    try:
                        event = self._external_cmd_queue.get(block=True, timeout=timeout)
                        logger.debug(f"user chose {event}")
                    except Empty:
                        logger.info(f"no user input within {timeout}s so assume to confirm")

                        event = "next"

                    self._workflow_jobmodel._status_sm.send(event)
                elif self._workflow_jobmodel._status_sm.current_state == ProcessingMachine.capture and isinstance(
                    self._workflow_jobmodel, JobModelVideo
                ):
                    timeout = self._workflow_jobmodel._configuration_set.processing.video_duration
                    try:
                        event = self._external_cmd_queue.get(block=True, timeout=timeout)
                        logger.debug(f"user chose {event}")
                        # continue if external_cmd_queue has an event
                    except Empty:
                        # after timeout
                        logger.info(f"no user input within {timeout}s so stopping video")
                        event = "next"

                    self._workflow_jobmodel._status_sm.send(event)
                else:
                    self._workflow_jobmodel._status_sm.send("next")

            logger.debug("job finished")
        except Exception as exc:
            logger.exception(exc)
            logger.error(f"the job failed, error: {exc}")

            sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="negative",
                    message="Please try again. Check the logs if the error is permanent!",
                    caption="Error processing the job 😔",
                )
            )
            sse_service.dispatch_event(SseEventProcessStateinfo(None, None, None))

        finally:
            self._workflow_jobmodel = None
            # send empty response to ui so it knows it's in idle again.

        logger.debug("_process_fun left")

    def _start_job(self, job_model: JobModelImage | JobModelCollage | JobModelAnimation | JobModelVideo | JobModelMulticamera):
        ## preflight checks
        self._check_occupied()

        logger.info(f"starting job model: {job_model=}")
        self._workflow_jobmodel = job_model

        # add listener to the job
        self._workflow_jobmodel._status_sm.add_listener(FrontendNotifierEventHooks())  # 1st listener executed,
        self._workflow_jobmodel._status_sm.add_listener(PluginEventHooks())  # 2nd
        self._workflow_jobmodel._status_sm.add_listener(MachineChangeListenter())  # 3rd
        self._workflow_jobmodel._status_sm.add_listener(DbListenter(self._mediacollection_service))  # 4rd, then machine, then model.

        ## run in separate thread
        logger.debug("starting _process_thread")
        self._process_thread = Thread(name="_processingservice_thread", target=self._process_fun, args=(), daemon=True)
        self._process_thread.start()

    # ##
    def initial_emit(self):
        # on init if never a job ran, model could not be avail.
        # if a job is currently running and during that a client connects, if will receive the self.model
        if self._workflow_jobmodel:
            source = self._workflow_jobmodel._status_sm.current_state
            target = self._workflow_jobmodel._status_sm.current_state
            sse_service.dispatch_event(SseEventProcessStateinfo(source, target, self._workflow_jobmodel))

    def _get_config_by_index(self, configurationset, index: int):
        try:
            return configurationset[index]
        except Exception as exc:
            logger.critical(f"could not find action configuration with index {index} in {configurationset}, error {exc}")
            raise exc

    def trigger_action(self, action_type: ActionType, action_index: int = 0):
        logger.info(f"trigger {action_type=}, {action_index=}")

        if action_type == "image":
            self._start_job(JobModelImage(self._get_config_by_index(appconfig.actions.image, action_index), self._aquisition_service))
        elif action_type == "collage":
            self._start_job(JobModelCollage(self._get_config_by_index(appconfig.actions.collage, action_index), self._aquisition_service))
        elif action_type == "animation":
            self._start_job(JobModelAnimation(self._get_config_by_index(appconfig.actions.animation, action_index), self._aquisition_service))
        elif action_type == "video":
            self._start_job(JobModelVideo(self._get_config_by_index(appconfig.actions.video, action_index), self._aquisition_service))
        elif action_type == "multicamera":
            self._start_job(JobModelMulticamera(self._get_config_by_index(appconfig.actions.multicamera, action_index), self._aquisition_service))

        self._information_service.stats_counter_increment(action_type)

    def wait_until_job_finished(self):
        if self._process_thread is None:
            raise RuntimeError("no job running currently to wait for")

        self._process_thread.join()

    def get_capture(self, capture_id: UUID) -> Capture:
        if not self._workflow_jobmodel:
            raise RuntimeError("no job ongoing, cannot get capture!")

        flattened_captures_list = [x for xs in self._workflow_jobmodel._capture_sets for x in xs.captures]

        for capture in flattened_captures_list:
            if capture.uuid == capture_id:
                return capture

        raise FileNotFoundError(f"cannot find {capture_id} in capture_set")

    def queue_external_event(self, event: Literal["next", "reject", "abort"]):
        if not self._workflow_jobmodel:
            raise RuntimeError("no job ongoing, cannot send event!")

        self._external_cmd_queue.put(event)

    def continue_process(self):
        self.queue_external_event("next")

    def reject_capture(self):
        self.queue_external_event("reject")

    def abort_process(self):
        self.queue_external_event("abort")
