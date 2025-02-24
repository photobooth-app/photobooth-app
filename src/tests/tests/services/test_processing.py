import logging
import time
from collections.abc import Generator

import pytest

from photobooth.appconfig import appconfig
from photobooth.container import Container, container
from photobooth.services.processing import ProcessingService

from ..util import video_duration

logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Generator[Container, None, None]:
    # setup
    container.start()

    # ensure video backend is running, otherwise tests can fail on slower devices like rpi4
    container.aquisition_service._get_video_backend().block_until_device_is_running()

    # deliver
    yield container
    container.stop()


class ConfirmRejectUserinputObserver:
    def __init__(self, processing_service: ProcessingService, abortjob: bool = False):
        self.processing_service: ProcessingService = processing_service
        self.abortjob: bool = abortjob  # if true, the job is aborted instead confirmed/rejected by simulated user.
        # internal flags
        self.rejected_once: bool = False  # reject once to test reject, then confirm

    def after_transition(self, event, source, target):
        logger.info(f"transition after: {source.id}--({event})-->{target.id}")

    def before_transition(self, target, event):
        logger.info(f"enter: {target.id} from {event}")

        if target.id == "approve_capture":
            if self.abortjob:
                logger.info("simulate user aborting job")
                self.processing_service.abort_process()
            elif not self.rejected_once:
                self.rejected_once = True
                logger.info("simulate user rejecting capture")
                self.processing_service.reject_capture()
            else:
                logger.info("simulate user confirming capture")
                self.processing_service.confirm_capture()


def test_capture(_container: Container):
    """this function processes single images (in contrast to collages or videos)"""

    container.processing_service.trigger_action("image", 0)

    assert _container.processing_service._state_machine is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None


def test_capture_zero_countdown(_container: Container):
    """this function processes single images (in contrast to collages or videos)"""
    appconfig.actions.image[0].jobcontrol.countdown_capture = 0

    _container.processing_service.trigger_action("image", 0)

    assert _container.processing_service._state_machine is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None


def test_collage_auto_approval(_container: Container):
    appconfig.actions.collage[0].jobcontrol.ask_approval_each_capture = False

    _container.processing_service.trigger_action("collage", 0)

    assert _container.processing_service._state_machine is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None


def test_collage_manual_approval(_container: Container):
    before_count = _container.mediacollection_service.count()
    correct_after_count = before_count + 3  # there are 2 captures plus final collage, one image is rejected, that shall be deleted again

    appconfig.actions.collage[0].jobcontrol.ask_approval_each_capture = True

    # starts in separate thread
    _container.processing_service.trigger_action("collage", 0)

    # observer that is used to confirm the captures.
    assert _container.processing_service._state_machine is not None  # statemachine was created after trigger_action
    _container.processing_service._state_machine.add_listener(ConfirmRejectUserinputObserver(_container.processing_service))

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None

    assert correct_after_count == _container.mediacollection_service.count()


def test_collage_manual_abort(_container: Container):
    before_count = _container.mediacollection_service.count()
    correct_after_count = before_count  # there is one capture made but then abort. should have 0 items added

    appconfig.actions.collage[0].jobcontrol.ask_approval_each_capture = True

    _container.processing_service.trigger_action("collage", 0)

    assert _container.processing_service._state_machine is not None
    _container.processing_service._state_machine.add_listener(ConfirmRejectUserinputObserver(_container.processing_service, abortjob=True))

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None

    assert correct_after_count == _container.mediacollection_service.count()


def test_animation(_container: Container):
    _container.processing_service.trigger_action("animation", 0)

    assert _container.processing_service._state_machine is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None


def test_video(_container: Container):
    _container.processing_service.trigger_action("video", 0)

    assert _container.processing_service._state_machine is not None
    number_of_images_before = _container.mediacollection_service.count()

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None

    assert _container.mediacollection_service.count() == number_of_images_before + 1

    video_item = _container.mediacollection_service.get_item_latest()

    # boomerang reverses video so double length
    in_dur = appconfig.actions.video[0].processing.video_duration
    out_dur = video_duration(video_item.unprocessed)

    # ensure written video is about in tolerance duration
    assert out_dur == pytest.approx(in_dur * 2.0, 0.3)


def test_video_stop_early(_container: Container):
    _container.processing_service.trigger_action("video", 0)

    assert _container.processing_service._state_machine is not None
    number_of_images_before = _container.mediacollection_service.count()

    # wait until actually recording
    timeout_counter = 0
    while not _container.aquisition_service.is_recording():
        time.sleep(0.05)
        timeout_counter += 0.05
        if timeout_counter > 10:
            raise RuntimeError("timed out waiting for record to start!")

    # recording active, wait 3 secs before stopping.
    desired_video_duration = 3
    time.sleep(desired_video_duration)
    _container.processing_service.trigger_action("video", 0)
    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None

    assert _container.mediacollection_service.count() == number_of_images_before + 1

    video_item = _container.mediacollection_service.get_item_latest()

    # ensure written video is about in tolerance duration
    video_duration_seconds = abs(round(video_duration(video_item.unprocessed), 1))
    logger.info(f"{video_duration_seconds=}")

    # boomerang reverses video so double length
    if appconfig.actions.video[0].processing.boomerang:
        desired_video_duration *= 2
    assert video_duration_seconds == pytest.approx(desired_video_duration, 0.5)


def test_multicamera(_container: Container):
    number_of_images_before = _container.mediacollection_service.count()

    _container.processing_service.trigger_action("multicamera", 0)

    assert _container.processing_service._state_machine is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None

    assert _container.mediacollection_service.count() == number_of_images_before + 5
