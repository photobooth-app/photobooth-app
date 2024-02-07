"""
_summary_
"""
import logging
import os
import time
from threading import Thread

from statemachine import State, StateMachine

from ..utils.exceptions import ProcessMachineOccupiedError
from .aquisitionservice import AquisitionService
from .baseservice import BaseService
from .config import appconfig
from .mediacollection.mediaitem import MediaItem, MediaItemTypes, get_new_filename
from .mediacollectionservice import (
    MediacollectionService,
)
from .mediaprocessingservice import MediaprocessingService
from .processing.jobmodels import JobModel
from .sseservice import SseEventFrontendNotification, SseEventProcessStateinfo, SseService
from .wledservice import WledService

logger = logging.getLogger(__name__)


class ProcessingService(BaseService):
    """_summary_"""

    def __init__(
        self,
        sse_service: SseService,
        aquisition_service: AquisitionService,
        mediacollection_service: MediacollectionService,
        mediaprocessing_service: MediaprocessingService,
        wled_service: WledService,
    ):
        super().__init__(sse_service)
        self._aquisition_service: AquisitionService = aquisition_service
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._mediaprocessing_service: MediaprocessingService = mediaprocessing_service
        self._wled_service: WledService = wled_service

        # objects
        self._state_machine: ProcessingMachine = None
        self._process_thread: Thread = None

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
            raise exc

            # TODO: handle rollback self._reset()

        finally:
            self._state_machine = None
            # send empty response to ui so it knows it's in idle again.
            self._sse_service.dispatch_event(SseEventProcessStateinfo(None))

        logger.debug("_process_fun left")

    ### external functions to start processes

    def start_job(self, jobmodel_typ, number_of_captures_to_take):
        ## preflight checks
        self._check_occupied()

        ## setup job
        job_model = JobModel()
        logger.info(f"set up job to start: {jobmodel_typ=}, {number_of_captures_to_take=}")

        job_model.start_model(
            jobmodel_typ,
            number_of_captures_to_take,
            collage_automatic_capture_continue=appconfig.common.collage_automatic_capture_continue,
        )

        ## init statemachine
        self._state_machine = ProcessingMachine(
            self._sse_service,
            self._aquisition_service,
            self._mediacollection_service,
            self._mediaprocessing_service,
            self._wled_service,
            job_model,
        )

        logger.info(f"start job {job_model}")

        ## run in separate thread
        logger.debug("starting _process_thread")
        self._process_thread = Thread(name="_process_thread", target=self._process_fun, args=(), daemon=True)
        self._process_thread.start()

    ##
    def initial_emit(self):
        # on init if never a job ran, model could not be avail.
        # if a job is currently running and during that a client connects, if will receive the self.model
        if self._state_machine:
            self._state_machine._emit_model_state_update()

    def start_job_1pic(self):
        self.start_job(JobModel.Typ.image, 1)

    def start_job_collage(self):
        self.start_job(JobModel.Typ.collage, self._mediaprocessing_service.number_of_captures_to_take_for_collage())

    def start_job_animation(self):
        self.start_job(JobModel.Typ.animation, self._mediaprocessing_service.number_of_captures_to_take_for_animation())

    def start_job_video(self):
        self.start_job(JobModel.Typ.video, 1)

    def wait_until_job_finished(self):
        if self._process_thread is None:
            raise RuntimeError("no job running currently to wait for")

        self._process_thread.join()

    def send_event(self, event: str):
        if not self._state_machine:
            raise RuntimeError("no job ongoing, cannot send event!")

        try:
            self._state_machine.send(event)
        except Exception as exc:
            logger.exception(exc)
            logger.warning(f"cannot confirm, error: {exc}")
            raise exc

    def confirm_capture(self):
        self.send_event("confirm")

    def reject_capture(self):
        self.send_event("reject")

    def abort_process(self):
        self.send_event("abort")

    def stop_recording(self):
        pass
        # TODO: implement


class ProcessingMachine(StateMachine):
    """ """

    ## STATES

    idle = State(initial=True)
    counting = State()  # countdown before capture
    capture = State()  # capture from camera include postprocess single img postproc
    record = State()  # record from camera
    approve_capture = State()  # waiting state to approve. transition by confirm,reject or autoconfirm
    captures_completed = State()  # final postproc (mostly to create collage/gif)
    present_capture = State()  # final presentation of mediaitem
    finished = State(final=True)  # final state
    ## TRANSITIONS

    start = idle.to(counting)
    _counted = counting.to(capture, unless="jobtype_recording") | counting.to(record, cond="jobtype_recording")
    _captured = capture.to(approve_capture) | record.to(captures_completed)
    confirm = approve_capture.to(counting, unless="all_captures_confirmed") | approve_capture.to(captures_completed, cond="all_captures_confirmed")
    reject = approve_capture.to(counting)
    abort = approve_capture.to(finished)
    _present = captures_completed.to(present_capture)
    _finish = present_capture.to(finished)

    def __init__(
        self,
        sse_service: SseService,
        aquisition_service: AquisitionService,
        mediacollection_service: MediacollectionService,
        mediaprocessing_service: MediaprocessingService,
        wled_service: WledService,
        jobmodel: JobModel,
    ):
        self._sse_service: SseService = sse_service
        self._aquisition_service: AquisitionService = aquisition_service
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._mediaprocessing_service: MediaprocessingService = mediaprocessing_service
        self._wled_service: WledService = wled_service

        self.model: JobModel  # for linting, initialized in super-class actually below

        # # call StateMachine init fun
        super().__init__(model=jobmodel)

    ## state actions

    def _emit_model_state_update(self):
        # always send current state on enter so UI can react (display texts, wait message on postproc, ...)
        self._sse_service.dispatch_event(SseEventProcessStateinfo(self.model))

    def after_transition(self, event, source, target):
        logger.info(f"transition after: {source.id}--({event})-->{target.id}")

    def on_enter_state(self, event, target):
        """_summary_"""
        logger.info(f"enter: {target.id} from {event}")

        # always send current state on enter so UI can react (display texts, wait message on postproc, ...)
        self._emit_model_state_update()

    def on_exit_state(self, event, state):
        """_summary_"""
        logger.info(f"exit: {state.id} from {event}")

    def on_exit_idle(self):
        # when idle left, check that all is properly set up!

        if not self.model._validate_job():
            logger.error(self.model)
            raise RuntimeError("job setup illegal")

    def on_enter_idle(self):
        """_summary_"""
        logger.info("state idle entered.")

        self._wled_service.preset_standby()

        # switch backend to preview mode always when returning to idle.
        self._aquisition_service.signalbackend_configure_optimized_for_idle()

    def on_enter_counting(self):
        """_summary_"""
        # wled signaling
        self._wled_service.preset_thrill()

        # set backends to capture mode; backends take their own actions if needed.
        if self.model._typ is not JobModel.Typ.video:
            # signal the backend we need hq still in every case, except video.
            self._aquisition_service.signalbackend_configure_optimized_for_hq_capture()

        # determine countdown time, first and following could have different times
        duration = (
            appconfig.common.countdown_capture_first
            if (self.model.number_captures_taken() == 0)
            else appconfig.common.countdown_capture_second_following
        )

        # if countdown is 0, skip following and transition to next state directy
        if duration == 0:
            logger.info("no timer, skip countdown")

            # leave this state by here
            self._counted()

            return
            # do not continue here again after counted has processed

        # starting countdown
        if (duration - appconfig.common.countdown_camera_capture_offset) <= 0:
            logger.warning("duration equal/shorter than camera offset makes no sense. this results in 0s countdown!")

        logger.info(f"start countdown, duration_user={duration=}, offset_camera={appconfig.common.countdown_camera_capture_offset}")
        self.model.start_countdown(
            duration_user=duration,
            offset_camera=appconfig.common.countdown_camera_capture_offset,
        )
        # inform UI to count
        self._sse_service.dispatch_event(SseEventProcessStateinfo(self.model))

        # wait for countdown finished before continue machine
        self.model.wait_countdown_finished()  # blocking call

        # and now go on
        self._counted()

    def on_enter_capture(self):
        """_summary_"""
        logger.info(
            f"current capture ({self.model.number_captures_taken()+1}/{self.model.total_captures_to_take()}, "
            f"remaining {self.model.remaining_captures_to_take()-1})"
        )

        # depending on job type we have slightly different filenames so it can be distinguished in the UI later.
        # 1st phase is about capture, so always image - but distinguish between other types so UI can handle different later
        _type = MediaItemTypes.image
        _visibility = True
        if self.model._typ is JobModel.Typ.collage:
            _type = MediaItemTypes.collageimage  # 1st phase collage image
            _visibility = appconfig.common.gallery_show_individual_images
        if self.model._typ is JobModel.Typ.animation:
            _type = MediaItemTypes.animationimage  # 1st phase animation image
            _visibility = appconfig.common.gallery_show_individual_images
        if self.model._typ is JobModel.Typ.video:
            raise RuntimeError("videos are not processed in capture state")

        filepath_neworiginalfile = get_new_filename(type=_type, visibility=_visibility)
        logger.debug(f"capture to {filepath_neworiginalfile=}")

        start_time_capture = time.time()
        image_bytes = self._aquisition_service.wait_for_hq_image()  # this function repeats to get images if one capture fails.

        with open(filepath_neworiginalfile, "wb") as file:
            file.write(image_bytes)

        # populate image item for further processing:
        mediaitem = MediaItem(os.path.basename(filepath_neworiginalfile))
        self.model.set_last_capture(mediaitem)

        logger.info(f"-- process time: {round((time.time() - start_time_capture), 2)}s to capture still")

        # capture finished, go to next state
        self._captured()

    def on_exit_capture(self):
        """_summary_"""

        if not self.model.last_capture_successful():
            logger.critical("on_exit_capture no valid image taken! abort processing")
            # TODO:self._reset()
            return

        ## PHASE 1:
        # postprocess each capture individually
        logger.info("start postprocessing phase 1")

        # load last mediaitem for further processing
        mediaitem = self.model.get_last_capture()
        logger.info(f"postprocessing last capture: {mediaitem=}")

        # always create unprocessed versions for later usage
        tms = time.time()
        mediaitem.create_fileset_unprocessed()
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create scaled images")

        # apply 1pic pipeline:
        tms = time.time()
        self._mediaprocessing_service.process_image_collageimage_animationimage(mediaitem, self.model.number_captures_taken())
        logger.info(f"-- process time: {round((time.time() - tms), 2)}s to process singleimage")

        if not mediaitem.fileset_valid():
            raise RuntimeError("created fileset invalid! check logs for additional errors")

        logger.info(f"capture {mediaitem=} successful")

        # add to collection
        self.model.add_confirmed_capture_to_collection(self.model.get_last_capture())

    def on_enter_approve_capture(self):
        # if job is collage, each single capture could be confirmed or not:
        if self.model.ask_user_for_approval():
            # present capture with buttons to approve.
            logger.info("finished capture, present to user to confirm, reject or abort")
        else:
            # auto continue
            logger.info("finished capture, automatic confirm enabled")
            self.confirm()

    def on_exit_approve_capture(self, event):
        if event == self.confirm.name:
            # nothing to do
            pass

        if event == self.reject.name:
            # remove rejected image
            delete_mediaitem = self.model._confirmed_captures_collection.pop()
            self.model.set_last_capture(None)
            logger.info(f"rejected: {delete_mediaitem=}")
            self._mediacollection_service.delete_mediaitem_files(delete_mediaitem)

        if event == self.abort.name:
            # remove all images captured until now
            logger.info("aborting job, deleting captured items")
            for item in self.model._confirmed_captures_collection:
                logger.debug(f"delete item {item}")
                self._mediacollection_service.delete_mediaitem_files(mediaitem=item)

    def on_enter_record(self):
        """_summary_"""

        self._wled_service.preset_record()

        self._aquisition_service.start_recording()

        # capture finished, go to next state
        time.sleep(appconfig.misc.video_duration)

        self._captured()

    def on_exit_record(self):
        """_summary_"""

        self._wled_service.preset_standby()

        self._aquisition_service.stop_recording()

    def on_enter_captures_completed(self):
        ## PHASE 2:
        # postprocess job as whole, create collage of single images, video...
        logger.info("start postprocessing phase 2")

        if self.model._typ is JobModel.Typ.collage:
            # apply collage phase2 pipeline:
            tms = time.time()

            # pass copy to process_collage, so it cannot alter the model here (.pop() is called)
            mediaitem = self._mediaprocessing_service.create_collage(self.model._confirmed_captures_collection.copy())

            logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create collage")

            # resulting collage mediaitem will be added to the collection as most recent item
            self.model.add_confirmed_capture_to_collection(mediaitem)
            self.model.set_last_capture(mediaitem)  # set last item also to collage, so UI can rely on last capture being the one to present

        elif self.model._typ is JobModel.Typ.animation:
            # apply animation phase2 pipeline:
            tms = time.time()

            # pass copy to process_collage, so it cannot alter the model here (.pop() is called)
            mediaitem = self._mediaprocessing_service.create_animation(self.model._confirmed_captures_collection.copy())

            logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create animation")

            # resulting collage mediaitem will be added to the collection as most recent item
            self.model.add_confirmed_capture_to_collection(mediaitem)
            self.model.set_last_capture(mediaitem)  # set last item also to collage, so UI can rely on last capture being the one to present

        elif self.model._typ is JobModel.Typ.video:
            # apply video phase2 pipeline:
            tms = time.time()

            # get video in h264 format for further processing.
            temp_videofilepath = self._aquisition_service.get_recorded_video()

            # populate image item for further processing:
            filepath_neworiginalfile = get_new_filename(type=MediaItemTypes.video)
            logger.debug(f"record to {filepath_neworiginalfile=}")

            os.rename(temp_videofilepath, filepath_neworiginalfile)
            mediaitem = MediaItem(os.path.basename(filepath_neworiginalfile))
            self.model.set_last_capture(mediaitem)

            mediaitem.create_fileset_unprocessed()
            mediaitem.copy_fileset_processed()

            logger.info(f"-- process time: {round((time.time() - tms), 2)}s to create video")

            # resulting collage mediaitem will be added to the collection as most recent item
            self.model.add_confirmed_capture_to_collection(mediaitem)

        else:
            pass
            # nothing to do for other job type

        ## FINISH:
        # to inform frontend about new image to display
        logger.info("finished postprocessing")

        ## add items to collection:
        logger.info("adding items to db")

        for item in self.model._confirmed_captures_collection:
            logger.debug(f"adding {item} to collection")
            _ = self._mediacollection_service.db_add_item(item)

        # present to ui
        self._present()

    def on_enter_present_capture(self):
        self._finish()

    def on_enter_finished(self):
        # final state, nothing to do. just for UI to have a dedicated state.
        pass
