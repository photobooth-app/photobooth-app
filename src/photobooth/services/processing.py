import logging
from collections.abc import Mapping
from queue import Empty, Full, Queue
from threading import Event as threadingEvent
from threading import Thread
from typing import Literal
from uuid import UUID

from statemachine import Event, State

from ..appconfig import appconfig
from ..plugins import pm as pluggy_pm
from ..utils.exceptions import ProcessMachineOccupiedError
from .acquisition import AcquisitionService
from .base import BaseService
from .collection import MediacollectionService
from .config.groups.actions import MultiImageJobControl
from .information import InformationService
from .processor.animation import JobModelAnimation
from .processor.base import Capture, JobModelBase
from .processor.collage import JobModelCollage
from .processor.image import JobModelImage
from .processor.machine.processingmachine import ProcessingMachine, userEvents
from .processor.multicamera import JobModelMulticamera
from .processor.video import JobModelVideo
from .sse import sse_service
from .sse.sse_ import SseEventProcessStateinfo, SseEventTranslateableFrontendNotification

logger = logging.getLogger(__name__)


ActionType = Literal["image", "collage", "animation", "video", "multicamera"]
JobModelType = JobModelImage | JobModelCollage | JobModelAnimation | JobModelVideo | JobModelMulticamera
ACTION_TO_MODEL: Mapping[ActionType, type[JobModelType]] = {
    "image": JobModelImage,
    "collage": JobModelCollage,
    "animation": JobModelAnimation,
    "video": JobModelVideo,
    "multicamera": JobModelMulticamera,
}


class DbListenter:
    def __init__(self, mediacollection_service: MediacollectionService):
        self._mediacollection_service = mediacollection_service

    def on_exit_state(self, source: State, target: State, model: JobModelBase):
        if source.id == ProcessingMachine.completed.id:
            if model._result_mediaitems:
                logger.info(f"add {len(model._result_mediaitems)} results to db")

                for items in model._result_mediaitems:
                    self._mediacollection_service.add_item(items)  # and to the db.


class PluginEventHooks:
    def __init__(self):
        # https://python-statemachine.readthedocs.io/en/latest/actions.html#ordering
        pass

    def before_transition(self, source: State, target: State, event: Event, model: JobModelBase):
        pluggy_pm.hook.sm_before_transition(source=source, target=target, event=event, mediaitem_type=model._media_type)

    def on_exit_state(self, source: State, target: State, event: Event, model: JobModelBase):
        pluggy_pm.hook.sm_on_exit_state(source=source, target=target, event=event, mediaitem_type=model._media_type)

    def on_transition(self, source: State, target: State, event: Event, model: JobModelBase):
        pluggy_pm.hook.sm_on_transition(source=source, target=target, event=event, mediaitem_type=model._media_type)

    def on_enter_state(self, source: State, target: State, event: Event, model: JobModelBase):
        pluggy_pm.hook.sm_on_enter_state(source=source, target=target, event=event, mediaitem_type=model._media_type)

    def after_transition(self, source: State, target: State, event: Event, model: JobModelBase):
        pluggy_pm.hook.sm_after_transition(source=source, target=target, event=event, mediaitem_type=model._media_type)


class FrontendNotifierEventHooks:
    emit_before_transition_to_target = (ProcessingMachine.completed,)  # emit before processing to allow UI show processing on target=completed

    def before_transition(self, source: State, target: State, model):
        if target in self.emit_before_transition_to_target:
            # logger.info(f"send frontend notification {source=} {target=}") # might uncomment during debugging only
            sse_service.dispatch_event(SseEventProcessStateinfo(source=source, target=target, jobmodel=model))

    def after_transition(self, source: State, target: State, model):
        if target not in self.emit_before_transition_to_target:
            # logger.info(f"send frontend notification {source=} {target=}") # might uncomment during debugging only
            sse_service.dispatch_event(SseEventProcessStateinfo(source=source, target=target, jobmodel=model))


class ProcessingService(BaseService):
    def __init__(
        self,
        acquisition_service: AcquisitionService,
        mediacollection_service: MediacollectionService,
        information_service: InformationService,
    ):
        super().__init__()

        self._acquisition_service: AcquisitionService = acquisition_service
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._information_service: InformationService = information_service

        # objects
        self._workflow_jobmodel: JobModelType | None = None
        self._process_thread: Thread | None = None

        # external commands (next/reject/abort) can be sent from frontend api endpoints or gpio.
        # once a cmd is required, the user answer is queued and read by the job processor to continue as requested
        self._external_cmd_queue: Queue[userEvents] = Queue(maxsize=1)
        self._external_cmd_required: threadingEvent = threadingEvent()

    def start(self):
        super().start()

        pass

        super().started()

    def stop(self):
        super().stop()

        pass

        super().stopped()

    def _is_occupied(self) -> bool:
        return self._workflow_jobmodel is not None

    def _check_occupied(self):
        if self._is_occupied():
            # Job ongoing ⌛There is already a job running. Please wait until it finished.
            sse_service.dispatch_event(SseEventTranslateableFrontendNotification(color="negative", message_key="processing.machine_occupied"))
            raise ProcessMachineOccupiedError("bad request, only one request at a time!")

    def is_user_input_requested(self) -> bool:
        """if queue is initialized on _external_cmd_queue, a user request is waited for."""
        return self._external_cmd_required.is_set()

    def _request_user_input(self, timeout: float) -> userEvents:
        # reset queue to new instance to ensure there is nothing old in there for whatever reason...
        self._external_cmd_queue = Queue(1)

        # inform external functions that they should send an event now to the queue
        self._external_cmd_required.set()

        try:
            event = self._external_cmd_queue.get(block=True, timeout=timeout)
            logger.debug(f"user chose {event}")
        except Empty:
            logger.info(f"no user input within {timeout}s so assume to continue next")
            event = "next"
        finally:
            # clear the event queue, which indicates events sending not possible for externals
            pass

        return event

    def _process_fun(self):
        assert self._workflow_jobmodel
        assert self._workflow_jobmodel._status_sm.current_state == ProcessingMachine.initial_state

        try:
            while not self._workflow_jobmodel._status_sm.current_state == ProcessingMachine.finished:
                if self._workflow_jobmodel._status_sm.current_state == ProcessingMachine.approval:
                    assert isinstance(self._workflow_jobmodel._configuration_set.jobcontrol, MultiImageJobControl)

                    event = self._request_user_input(timeout=self._workflow_jobmodel._configuration_set.jobcontrol.approve_autoconfirm_timeout)
                    self._workflow_jobmodel._status_sm.send(event)

                elif self._workflow_jobmodel._status_sm.current_state == ProcessingMachine.capture and isinstance(
                    self._workflow_jobmodel, JobModelVideo
                ):
                    event = self._request_user_input(timeout=self._workflow_jobmodel._configuration_set.processing.video_duration)
                    event = event if event != "reject" else "next"  # force next if reject because reject is not an allowed transition
                    self._workflow_jobmodel._status_sm.send(event)
                else:
                    self._workflow_jobmodel._status_sm.send("next")

        except Exception as exc:
            logger.exception(exc)
            logger.error(f"the job failed, error: {exc}")

            # Error processing the job 😔 Please try again. Check the logs if the error is permanent!
            sse_service.dispatch_event(SseEventTranslateableFrontendNotification(color="negative", message_key="processing.job_failed"))
            sse_service.dispatch_event(SseEventProcessStateinfo(None, None, None))

        finally:
            self._workflow_jobmodel = None
            # send empty response to ui so it knows it's in idle again.

    def initial_emit(self):
        # on init if never a job ran, model could not be avail.
        # if a job is currently running and during that a client connects, if will receive the self.model
        if self._workflow_jobmodel:
            source = self._workflow_jobmodel._status_sm.current_state
            target = self._workflow_jobmodel._status_sm.current_state
            sse_service.dispatch_event(SseEventProcessStateinfo(source, target, self._workflow_jobmodel))

    def trigger_action(self, action_type: ActionType, action_index: int = 0):
        ## preflight checks
        self._check_occupied()

        jobmodel = ACTION_TO_MODEL[action_type](
            configuration_set=getattr(appconfig.actions, action_type)[action_index],
            acquisition_service=self._acquisition_service,
        )

        logger.info(f"trigger {action_type=}, {action_index=}, starting job model: {jobmodel=}")
        self._workflow_jobmodel = jobmodel

        # add listener to the job
        self._workflow_jobmodel._status_sm.add_listener(FrontendNotifierEventHooks())  # 1st listener executed,
        self._workflow_jobmodel._status_sm.add_listener(PluginEventHooks())  # 2nd
        self._workflow_jobmodel._status_sm.add_listener(DbListenter(self._mediacollection_service))  # 4rd, then machine, then model.

        ## run in separate thread
        self._process_thread = Thread(name="_processingservice_thread", target=self._process_fun, args=(), daemon=True)
        self._process_thread.start()

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

    def queue_external_event(self, event: userEvents):
        if not self._external_cmd_required.is_set():
            raise RuntimeError("currently no user input is requested!")

        try:
            self._external_cmd_queue.put_nowait(event)
            self._external_cmd_required.clear()
        except Full as exc:
            raise RuntimeError("cannot send the command because the queue is full") from exc

    def continue_process(self):
        self.queue_external_event("next")

    def reject_capture(self):
        self.queue_external_event("reject")

    def abort_process(self):
        self.queue_external_event("abort")
