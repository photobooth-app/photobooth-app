"""
_summary_
"""
import logging
import os
import time

from statemachine import State, StateMachine

from ..utils.exceptions import ProcessMachineOccupiedError
from .aquisitionservice import AquisitionService
from .config import appconfig
from .mediacollection.mediaitem import MediaItem, MediaItemTypes, get_new_filename
from .mediacollectionservice import (
    MediacollectionService,
)
from .mediaprocessingservice import MediaprocessingService
from .processing.jobmodels import JobModel
from .sseservice import SseEventProcessStateinfo, SseService
from .wledservice import WledService

logger = logging.getLogger(__name__)


class ProcessingService(StateMachine):
    """
    use it:
        machine.thrill()
        machine.shoot()
    """

    ## STATES

    idle = State(initial=True)
    counting = State()  # countdown before capture
    capture = State()  # capture from camera include postprocess single img postproc
    record = State()  # record from camera
    approve_capture = State()  # waiting state to approve. transition by confirm,reject or autoconfirm
    captures_completed = State()  # final postproc (mostly to create collage/gif)
    present_capture = State()  # final presentation of mediaitem

    ## TRANSITIONS

    start = idle.to(counting)
    _counted = counting.to(capture, unless="jobtype_recording") | counting.to(record, cond="jobtype_recording")
    _captured = capture.to(approve_capture) | record.to(captures_completed)
    confirm = approve_capture.to(counting, unless="all_captures_confirmed") | approve_capture.to(captures_completed, cond="all_captures_confirmed")
    reject = approve_capture.to(counting)
    _present = captures_completed.to(present_capture)
    _finalize = present_capture.to(idle)
    _reset = idle.to.itself(internal=True) | idle.from_(counting, capture, record, present_capture, approve_capture, captures_completed)

    def __init__(
        self,
        _sse_service: SseService,
        aquisition_service: AquisitionService,
        mediacollection_service: MediacollectionService,
        mediaprocessing_service: MediaprocessingService,
        wled_service: WledService,
    ):
        self._sse_service: SseService = _sse_service
        self._aquisition_service: AquisitionService = aquisition_service
        self._mediacollection_service: MediacollectionService = mediacollection_service
        self._mediaprocessing_service: MediaprocessingService = mediaprocessing_service
        self._wled_service: WledService = wled_service

        super().__init__(model=JobModel())

        # for proper linting
        self.model: JobModel

    ##
    def initial_emit(self):
        self._sse_service.dispatch_event(SseEventProcessStateinfo(self.model))

    ## transition actions

    def before_start(self, typ: JobModel.Typ, total_captures_to_take: int):
        assert isinstance(typ, JobModel.Typ)
        assert isinstance(total_captures_to_take, int)

        # reset old job data
        # job is reset on start only, not on enter_idle because the UI relies on the last model-data to present last item.
        self.model.reset_job()

        logger.info(f"set up job to start: {typ=}, {total_captures_to_take=}")

        self.model.start_model(
            typ,
            total_captures_to_take,
            collage_automatic_capture_continue=appconfig.common.collage_automatic_capture_continue,
            collage_hide_individual_pictures=appconfig.common.collage_hide_individual_pictures,
            collage_delete_individual_pictures=appconfig.common.collage_delete_individual_pictures,
        )

        logger.info(f"start job {self.model}")

    ## state actions

    def _emit_model_state_update(self):
        # always send current state on enter so UI can react (display texts, wait message on postproc, ...)
        self._sse_service.dispatch_event(SseEventProcessStateinfo(self.model))

    def on_enter_state(self, event, state):
        """_summary_"""
        # logger.info(f"Entering '{state.id}' state from '{event}' event.")
        logger.info(f"on_enter_state {self.current_state.id=} ")

        # always send current state on enter so UI can react (display texts, wait message on postproc, ...)
        self._emit_model_state_update()

    def on_exit_state(self, event, state):
        """_summary_"""
        # logger.info(f"Entering '{state.id}' state from '{event}' event.")
        logger.info(f"on_exit_state {self.current_state.id=} ")

        # don't emit on exit state again because UI would display approval twice. UI needs to know when next state is entered,
        # not leaving a state usually, if needed, on_exit_SPECIFIC-STATE would need to be created and emit model.
        # self._emit_model_state_update()

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
        if self.model._typ is JobModel.Typ.collage:
            _type = MediaItemTypes.collageimage  # 1st phase collage image
        if self.model._typ is JobModel.Typ.animation:
            _type = MediaItemTypes.animationimage  # 1st phase collage image
        if self.model._typ is JobModel.Typ.video:
            raise RuntimeError("videos are not processed in capture state")

        filepath_neworiginalfile = get_new_filename(type=_type)
        logger.debug(f"capture to {filepath_neworiginalfile=}")

        try:
            start_time_capture = time.time()
            image_bytes = self._aquisition_service.wait_for_hq_image()  # this function repeats to get images if one capture fails.

            with open(filepath_neworiginalfile, "wb") as file:
                file.write(image_bytes)

            # populate image item for further processing:
            mediaitem = MediaItem(os.path.basename(filepath_neworiginalfile))
            self.model.set_last_capture(mediaitem)

            logger.info(f"-- process time: {round((time.time() - start_time_capture), 2)}s to capture still")

        except Exception as exc:
            logger.exception(exc)
            logger.error(f"error capture image. {exc}")
            # can we do additional error handling here?

            # reraise so http error can be sent
            raise exc
            # no retry for this type of error

        # capture finished, go to next state
        self._captured()

    def on_exit_capture(self):
        """_summary_"""

        if not self.model.last_capture_successful():
            logger.critical("on_exit_capture no valid image taken! abort processing")
            self._reset()
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
            self.confirm_capture()

    def on_exit_approve_capture(self, event):
        if event == self.confirm.name:
            # nothing to do
            pass
            # add result to temporary confirmed collection
            # self.model.add_confirmed_capture_to_collection(self.model.get_last_capture())

        if event == self.reject.name:
            # remove rejected image
            delete_mediaitem = self.model._confirmed_captures_collection.pop()
            self.model.set_last_capture(None)
            logger.info(f"rejected: {delete_mediaitem=}")
            self._mediacollection_service.delete_mediaitem_files(delete_mediaitem)

    def on_enter_record(self):
        """_summary_"""

        self._wled_service.preset_record()

        try:
            self._aquisition_service.start_recording()

        except Exception as exc:
            logger.exception(exc)
            logger.error(f"error start recording! {exc}")

            # reraise so http error can be sent
            raise exc
            # no retry for this type of error

        # capture finished, go to next state
        time.sleep(appconfig.misc.video_duration)

        self._captured()

    def on_exit_record(self):
        """_summary_"""

        self._wled_service.preset_standby()

        try:
            self._aquisition_service.stop_recording()
        except Exception as exc:
            logger.exception(exc)
            logger.error(f"error stop recording! {exc}")

            # reraise so http error can be sent
            raise exc
            # no retry for this type of error

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

            # (optionally) hide individual images from gallery
            if self.model.hide_individual_images():
                while len(self.model._confirmed_captures_collection) > 0:
                    delete_mediaitem = self.model._confirmed_captures_collection.pop()
                    # (optionally) delete individual images
                    if self.model.delete_individual_images():
                        self._mediacollection_service.delete_mediaitem_files(delete_mediaitem)

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

        # send machine to idle again
        self._present()

    def on_exit_captures_completed(self):
        ## finish and add items to collection:
        #
        logger.info("exit job postprocess, adding items to db")

        for item in self.model._confirmed_captures_collection:
            logger.debug(f"adding {item} to collection")
            _ = self._mediacollection_service.db_add_item(item)

    def on_enter_present_capture(self):
        self._finalize()

    def on__reset(self):
        logger.info("job reset, rollback captures during job")

        for item in self.model._confirmed_captures_collection:
            logger.debug(f"delete item {item}")
            self._mediacollection_service.delete_mediaitem_files(mediaitem=item)

    def _check_occupied(self):
        if not self.idle.is_active:
            raise ProcessMachineOccupiedError("bad request, only one request at a time!")

    ### external functions to start processes

    def start_job_1pic(self):
        self._check_occupied()
        try:
            self.start(JobModel.Typ.image, 1)
        except Exception as exc:
            logger.error(exc)
            self._reset()
            raise RuntimeError(f"error processing the job :| {exc}") from exc

    def start_job_collage(self):
        self._check_occupied()
        try:
            self.start(JobModel.Typ.collage, self._mediaprocessing_service.number_of_captures_to_take_for_collage())
        except Exception as exc:
            logger.error(exc)
            self._reset()
            raise RuntimeError(f"error processing the job :| {exc}") from exc

    def start_job_video(self):
        self._check_occupied()
        try:
            self.start(JobModel.Typ.video, 1)
        except Exception as exc:
            logger.error(exc)
            self._reset()
            raise RuntimeError(f"error processing the job :| {exc}") from exc

    def start_job_animation(self):
        self._check_occupied()
        try:
            self.start(JobModel.Typ.animation, self._mediaprocessing_service.number_of_captures_to_take_for_animation())
        except Exception as exc:
            logger.error(exc)
            self._reset()
            raise RuntimeError(f"error processing the job :| {exc}") from exc

    def job_finished(self):
        return self.idle.is_active

    def confirm_capture(self):
        self.confirm()

    def reject_capture(self):
        self.reject()

    def abort_process(self):
        self._reset()

    def stop_recording(self):
        self._captured()
