"""
_summary_
"""

import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from statemachine import State, StateMachine

from .. import PATH_PROCESSED, PATH_UNPROCESSED
from ..database.models import Mediaitem, MediaitemTypes
from ..utils.exceptions import ProcessMachineOccupiedError
from .aquisition import AquisitionService
from .base import BaseService
from .collection import MediacollectionService
from .config import appconfig
from .information import InformationService
from .jobmodels.animation import JobModelAnimation
from .jobmodels.base import JobModelBase, action_type_literal
from .jobmodels.collage import JobModelCollage
from .jobmodels.image import JobModelImage
from .jobmodels.multicamera import JobModelMulticamera
from .jobmodels.video import JobModelVideo
from .mediaprocessing.processes import process_image_collageimage_animationimage, process_video
from .sse import SseEventFrontendNotification, SseEventProcessStateinfo, SseService
from .wled import WledService

logger = logging.getLogger(__name__)

MEDIAITEM_TYPE_TO_FILEENDING_MAPPING = {
    MediaitemTypes.image: "jpg",
    MediaitemTypes.collage: "jpg",
    MediaitemTypes.animation: "gif",
    MediaitemTypes.video: "mp4",
    MediaitemTypes.multicamera: "gif",
}


class ProcessingService(BaseService):
    """_summary_"""

    def __init__(
        self,
        sse_service: SseService,
        aquisition_service: AquisitionService,
        mediacollection_service: MediacollectionService,
        wled_service: WledService,
        information_service: InformationService,
    ):
        super().__init__(sse_service)

        self._aquisition_service: AquisitionService = aquisition_service
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._wled_service: WledService = wled_service
        self._information_service: InformationService = information_service

        # objects
        self._state_machine: ProcessingMachine = None
        self._process_thread: Thread = None
        self._external_cmd_queue: Queue = None

    def _check_occupied(self):
        if self._state_machine is not None:
            self._sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="info",
                    message="There is already a job running. Please wait until it finished.",
                    caption="Job in process ⌛",
                )
            )
            raise ProcessMachineOccupiedError("bad request, only one request at a time!")

    def _process_fun(self):
        try:
            logger.info("starting job")
            self._state_machine.start()
            logger.debug("job finished")
        except Exception as exc:
            logger.exception(exc)
            logger.error(f"the job failed, error: {exc}")

            self._sse_service.dispatch_event(
                SseEventFrontendNotification(
                    color="negative",
                    message="Please try again. Check the logs if the error is permanent!",
                    caption="Error processing the job 😔",
                )
            )
            self._sse_service.dispatch_event(SseEventProcessStateinfo(None))

            # removed raising exception because it's in a thread and reraising it will just create an uncaught exception but adds no value
            # raise exc

        finally:
            self._state_machine = None
            # send empty response to ui so it knows it's in idle again.

        logger.debug("_process_fun left")

    def _start_job(self, job_model):
        ## preflight checks
        self._check_occupied()

        logger.info(f"starting job model: {job_model=}")

        # start with clear queue
        self._external_cmd_queue = Queue()

        ## init statemachine
        self._state_machine = ProcessingMachine(
            self._sse_service,
            self._aquisition_service,
            self._mediacollection_service,
            self._wled_service,
            self._external_cmd_queue,
            job_model,
        )

        ## run in separate thread
        logger.debug("starting _process_thread")
        self._process_thread = Thread(name="_processingservice_thread", target=self._process_fun, args=(), daemon=True)
        self._process_thread.start()

    ##
    def initial_emit(self):
        # on init if never a job ran, model could not be avail.
        # if a job is currently running and during that a client connects, if will receive the self.model
        if self._state_machine:
            self._state_machine._emit_model_state_update()

    def _get_config_by_index(self, action_type: action_type_literal, index: int = 0):
        configurationsets = getattr(appconfig.actions, action_type, None)
        assert configurationsets is not None  # programming error, not raised but test in pytest
        if len(configurationsets) == 0:  # user config error, raised
            raise RuntimeError(f"Configuration error: {action_type} has no actions defined!")

        try:
            return configurationsets[index]
        except Exception as exc:
            logger.critical(f"could not find action configuration with index {index} in {configurationsets}, error {exc}")
            raise exc

    ### external functions to start processes

    def trigger_action(self, action_type: action_type_literal, action_index: int = 0):
        logger.info(f"trigger {action_type=}, {action_index=}")

        configurationset = self._get_config_by_index(action_type, action_index)

        if action_type == "image":
            self._start_job(JobModelImage(configurationset))
        elif action_type == "collage":
            self._start_job(JobModelCollage(configurationset))
        elif action_type == "animation":
            self._start_job(JobModelAnimation(configurationset))
        elif action_type == "video":
            if self._state_machine is not None:
                # stop_recording set the counter to 0 and doesn't affect other jobs somehow, so we can just set 0 in else.
                logger.info("running job, sending stop recording info")
                self.stop_recording()
            else:
                self._start_job(JobModelVideo(configurationset))
        elif action_type == "multicamera":
            self._start_job(JobModelMulticamera(configurationset))
        else:
            raise RuntimeError(f"illegal {action_type=}")

        self._information_service.stats_counter_increment(action_type)

    def wait_until_job_finished(self):
        if self._process_thread is None:
            raise RuntimeError("no job running currently to wait for")

        self._process_thread.join()

    def send_event(self, event: str):
        if not self._state_machine:
            raise RuntimeError("no job ongoing, cannot send event!")

        self._external_cmd_queue.put(event)

    def confirm_capture(self):
        self.send_event("confirm")

    def reject_capture(self):
        self.send_event("reject")

    def abort_process(self):
        self.send_event("abort")

    def stop_recording(self):
        self.send_event("stop_recording")


class ProcessingMachine(StateMachine):
    """ """

    ## STATES

    idle = State(initial=True)
    counting = State()  # countdown before capture
    capture = State()  # capture from camera include postprocess single img postproc
    multicapture = State()  # capture from multicapture backend
    record = State()  # record from camera
    approve_capture = State()  # waiting state to approve. transition by confirm,reject or autoconfirm
    captures_completed = State()  # final postproc (mostly to create collage/gif)
    present_capture = State()  # final presentation of mediaitem
    finished = State(final=True)  # final state
    ## TRANSITIONS

    start = idle.to(counting)
    _counted_capture = counting.to(capture)
    _counted_record = counting.to(record)
    _counted_multicapture = counting.to(multicapture)
    _captured = capture.to(approve_capture) | multicapture.to(approve_capture)
    confirm = approve_capture.to(counting, unless="all_captures_done") | approve_capture.to(captures_completed, cond="all_captures_done")
    reject = approve_capture.to(counting)
    abort = approve_capture.to(finished)
    stop_recording = record.to(captures_completed)
    _present = captures_completed.to(present_capture)
    _finish = present_capture.to(finished)

    def __init__(
        self,
        sse_service: SseService,
        aquisition_service: AquisitionService,
        mediacollection_service: MediacollectionService,
        wled_service: WledService,
        _external_cmd_queue: Queue,
        jobmodel: JobModelBase,
    ):
        self._sse_service: SseService = sse_service
        self._aquisition_service: AquisitionService = aquisition_service
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._wled_service: WledService = wled_service
        self._external_cmd_queue: Queue = _external_cmd_queue

        self.model: JobModelBase  # for linting, initialized in super-class actually below

        # # call StateMachine init fun
        super().__init__(model=jobmodel)

    ## state actions
    def _new_filename(self, media_type: MediaitemTypes):
        filename_ending = MEDIAITEM_TYPE_TO_FILEENDING_MAPPING[media_type]
        return f"{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')}.{filename_ending}"

    def _emit_model_state_update(self):
        # always send current state on enter so UI can react (display texts, wait message on postproc, ...)
        self._sse_service.dispatch_event(SseEventProcessStateinfo(self.model))

    def _update_captures_taken(self):
        number_captures_taken = len(self._mediacollection_service.get_items_relto_job(self.model._job_identifier))
        self.model.set_captures_taken(number_captures_taken)

    def after_transition(self, event, source, target):
        pass

    def on_enter_state(self, event, target):
        # always send current state on enter so UI can react (display texts, wait message on postproc, ...)
        self._emit_model_state_update()

    def on_exit_state(self, event, state):
        pass

    def on_exit_idle(self):
        pass

    def on_enter_idle(self):
        """_summary_"""
        logger.info("state idle entered.")

    def on_enter_counting(self):
        """_summary_"""
        # wled signaling
        self._wled_service.preset_thrill()

        # set backends to capture mode; backends take their own actions if needed.
        if isinstance(self.model, JobModelVideo):
            # signal the backend we need hq still in every case, except video.
            self._aquisition_service.signalbackend_configure_optimized_for_video()
        else:
            # signal the backend we need hq still in every case, except video.
            self._aquisition_service.signalbackend_configure_optimized_for_hq_preview()

        self.model.start_countdown(appconfig.backends.countdown_camera_capture_offset)
        logger.info(f"started countdown, duration={self.model._duration_user}, offset_camera={appconfig.backends.countdown_camera_capture_offset}")

        # inform UI to count
        self._sse_service.dispatch_event(SseEventProcessStateinfo(self.model))

        # wait for countdown finished before continue machine
        self.model.wait_countdown_finished()  # blocking call

        # and now go on
        if isinstance(self.model, JobModelVideo):
            self._counted_record()
        elif isinstance(self.model, JobModelMulticamera):
            self._counted_multicapture()
        else:
            self._counted_capture()

    def on_enter_capture(self):
        logger.info(
            f"current capture ({self.model.get_captures_taken() + 1}/{self.model.total_captures_to_take()}, "
            f"remaining {self.model.remaining_captures_to_take() - 1})"
        )

        self._aquisition_service.signalbackend_configure_optimized_for_hq_capture()

        start_time_capture = time.time()

        filepath = self._aquisition_service.wait_for_still_file()

        logger.info(f"-- process time: {round((time.time() - start_time_capture), 2)}s to capture still")

        ## PHASE 1:
        # postprocess each capture individually
        logger.info(f"postprocessing capture: {filepath=}")

        # depending on job type we have slightly different filenames so it can be distinguished in the UI later.
        # 1st phase is about capture, so always image - but distinguish between other types so UI can handle different later
        _show = getattr(self.model._configuration_set.jobcontrol, "show_individual_captures_in_gallery", True)
        _config = self.model.get_phase1_singlepicturedefinition_per_index(self.model.get_captures_taken()).model_dump(mode="json")

        original_filenamepath = self._new_filename(MediaitemTypes.image)
        mediaitem = Mediaitem(
            job_identifier=self.model._job_identifier,
            media_type=MediaitemTypes.image,
            unprocessed=Path(PATH_UNPROCESSED, original_filenamepath),
            processed=Path(PATH_PROCESSED, original_filenamepath),
            pipeline_config=_config,
            show_in_gallery=_show,
        )

        shutil.move(filepath, mediaitem.unprocessed)

        logger.debug(f"capture to {mediaitem.unprocessed=}")

        # apply 1pic pipeline:
        tms = time.time()
        process_image_collageimage_animationimage(mediaitem)

        assert mediaitem.unprocessed.is_file()
        assert mediaitem.processed.is_file()

        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to process singleimage")

        # add to collection
        # update model so it knows the latest number of captures and the machine can react accordingly if finished
        self._mediacollection_service.add_item(mediaitem)  # and to the db.
        self.model._last_captured_mediaitem_id = mediaitem.id
        self._update_captures_taken()

        logger.info(f"capture {mediaitem=} successful")

        # capture finished, go to next state
        self._captured()

    def on_enter_multicapture(self):
        # depending on job type we have slightly different filenames so it can be distinguished in the UI later.
        # 1st phase is about capture, so always image - but distinguish between other types so UI can handle different later
        _show = getattr(self.model._configuration_set.jobcontrol, "show_individual_captures_in_gallery", False)
        _config = self.model.get_phase1_singlepicturedefinition_per_index(self.model.get_captures_taken()).model_dump(mode="json")

        self._aquisition_service.signalbackend_configure_optimized_for_hq_capture()

        start_time_capture = time.time()

        filepaths = self._aquisition_service.wait_for_multicam_files()

        mediaitems: list[Mediaitem] = []
        for filepath in filepaths:
            original_filenamepath = self._new_filename(MediaitemTypes.image)
            mediaitem = Mediaitem(
                job_identifier=self.model._job_identifier,
                media_type=MediaitemTypes.image,
                unprocessed=Path(PATH_UNPROCESSED, original_filenamepath),
                processed=Path(PATH_PROCESSED, original_filenamepath),
                pipeline_config=_config,
                show_in_gallery=_show,
            )

            logger.debug(f"capture to {mediaitem.unprocessed=}")

            shutil.move(filepath, mediaitem.unprocessed)

            mediaitems.append(mediaitem)

        logger.info(f"-- process time: {round((time.time() - start_time_capture), 2)}s to capture still")

        # postprocess each capture individually
        logger.info("start postprocessing phase 1")

        # load last mediaitem for further processing
        logger.info(f"postprocessing last captures: {mediaitems=}")

        # always create unprocessed versions for later usage
        tms = time.time()
        for mediaitem in mediaitems:
            process_image_collageimage_animationimage(mediaitem)

            # add to collection
            self._mediacollection_service.add_item(mediaitem)  # and to the db.

        self.model._last_captured_mediaitem_id = mediaitems[-1].id
        self._update_captures_taken()

        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to process")
        logger.info(f"capture {mediaitem=} successful")

        # capture finished, go to next state
        self._captured()

    def on_enter_approve_capture(self):
        logger.info("finished capture")

        # if job is collage, each single capture could be confirmed or not:
        if self.model.ask_user_for_approval():
            # present capture with buttons to approve.
            logger.info(f"waiting {self.model._configuration_set.jobcontrol.approve_autoconfirm_timeout}s for user to confirm, reject or abort")

            try:
                event = self._external_cmd_queue.get(block=True, timeout=self.model._configuration_set.jobcontrol.approve_autoconfirm_timeout)
                logger.debug(f"user chose {event}")
            except Empty:
                logger.info(f"no user input within {self.model._configuration_set.jobcontrol.approve_autoconfirm_timeout}s so assume to confirm")

                event = "confirm"

            self.send(event)

        else:
            # auto continue
            logger.info("automatic confirm enabled")
            self.confirm()

    def on_exit_approve_capture(self, event):
        if event == self.confirm.name:
            # nothing to do
            pass

        if event == self.reject.name:
            # remove rejected image
            latest_item = self._mediacollection_service.get_item_latest()
            logger.info(f"rejected: {latest_item=}")
            self._mediacollection_service.delete_item(latest_item)

            self._update_captures_taken()

        if event == self.abort.name:
            # remove all images captured until now
            logger.info("aborting job, deleting captured items")

            job_items = self._mediacollection_service.get_items_relto_job(self.model._job_identifier)
            for job_item in job_items:
                self._mediacollection_service.delete_item(job_item)

    def on_enter_record(self):
        """_summary_"""

        self._wled_service.preset_record()

        self._aquisition_service.start_recording(self.model._configuration_set.processing.video_framerate)

        try:
            event = self._external_cmd_queue.get(block=True, timeout=float(self.model._configuration_set.processing.video_duration))
            logger.debug(f"user chose {event}")
            # continue if external_cmd_queue has an event
        except Empty:
            # after timeout
            logger.info(f"no user input within {self.model._configuration_set.processing.video_duration}s so stopping video")

        self.stop_recording()

    def on_exit_record(self):
        """_summary_"""

        self._wled_service.preset_standby()

        self._aquisition_service.stop_recording()

        # get video in h264 format for further processing.
        temp_videofilepath = self._aquisition_service.get_recorded_video()
        logger.debug(f"recorded to {temp_videofilepath=}")

        original_filenamepath = self._new_filename(self.model._media_type)
        mediaitem = Mediaitem(
            job_identifier=self.model._job_identifier,
            media_type=self.model._media_type,
            unprocessed=Path(PATH_UNPROCESSED, original_filenamepath),
            processed=Path(PATH_PROCESSED, original_filenamepath),
            pipeline_config=self.model._configuration_set.processing.model_dump(mode="json"),
        )

        # apply video phase2 pipeline:
        tms = time.time()
        process_video(temp_videofilepath, mediaitem)
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create video")

        # add to collection
        self._mediacollection_service.add_item(mediaitem)  # and to the db.
        self.model._last_captured_mediaitem_id = mediaitem.id

    def on_enter_captures_completed(self):
        # get phase 1 items:
        phase1_mediaitems = self._mediacollection_service.get_items_relto_job(self.model._job_identifier)
        assert len(phase1_mediaitems) > 0

        ## PHASE 2:
        # postprocess job as whole, create collage of single images, video...
        logger.info("start postprocessing phase 2")

        phase2_mediaitem: Mediaitem = None
        if isinstance(self.model, JobModelCollage | JobModelAnimation | JobModelMulticamera):
            original_filenamepath = self._new_filename(self.model._media_type)
            phase2_mediaitem = Mediaitem(
                job_identifier=self.model._job_identifier,
                media_type=self.model._media_type,
                unprocessed=Path(PATH_UNPROCESSED, original_filenamepath),
                processed=Path(PATH_PROCESSED, original_filenamepath),
                pipeline_config=self.model._configuration_set.processing.model_dump(mode="json"),
            )

            tms = time.time()
            self.model.do_phase2_process_and_generate(phase1_mediaitems, phase2_mediaitem)
            logger.info(f"-- process time: {round((time.time() - tms), 2)}s for phase 2")

        ## FINISH:
        # to inform frontend about new image to display
        logger.info("finished postprocessing")

        ## add galleryitems
        # finally add resulting collage mediaitem will be added to the collection as most recent item
        if phase2_mediaitem:
            self._mediacollection_service.add_item(phase2_mediaitem)
            self.model._last_captured_mediaitem_id = phase2_mediaitem.id

        # present to ui
        self._present()

    def on_enter_present_capture(self):
        self._finish()

    def on_enter_finished(self):
        # final state, nothing to do. just for UI to have a dedicated state.

        self._wled_service.preset_standby()

        # switch backend to preview mode always when returning to idle.
        self._aquisition_service.signalbackend_configure_optimized_for_idle()

        # TODO: send image to share service. the shareservice checks if any share is configured for autoshare and executes all of these
        # mediaitem = self.model.get_last_capture()
        # self._share_service.autoprint(mediaitem)
