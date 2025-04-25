import logging
import time
from collections.abc import Generator

import pytest
from PIL import Image

from photobooth.appconfig import appconfig
from photobooth.container import Container, container

from ..util import block_until_device_is_running, video_duration

logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Generator[Container, None, None]:
    # setup
    container.start()

    # ensure video backend is running, otherwise tests can fail on slower devices like rpi4
    block_until_device_is_running(container.aquisition_service._get_video_backend())

    # deliver
    yield container
    container.stop()


def wait_for_user_input_requested():
    if not container.processing_service._external_cmd_required.wait(timeout=5):
        raise RuntimeError("waiting for user input not within timeout")


def test_capture(_container: Container):
    """this function processes single images (in contrast to collages or videos)"""

    container.processing_service.trigger_action("image", 0)

    assert _container.processing_service._workflow_jobmodel is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._workflow_jobmodel is None

    phase2_item = _container.mediacollection_service.get_item_latest()
    assert phase2_item.unprocessed.suffix.lower() == ".jpg"

    with Image.open(phase2_item.unprocessed, formats=["JPEG"]) as img:
        img.verify()


def test_capture_zero_countdown(_container: Container):
    """this function processes single images (in contrast to collages or videos)"""
    appconfig.actions.image[0].jobcontrol.countdown_capture = 0

    _container.processing_service.trigger_action("image", 0)

    assert _container.processing_service._workflow_jobmodel is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._workflow_jobmodel is None


def test_collage_auto_approval(_container: Container):
    appconfig.actions.collage[0].jobcontrol.ask_approval_each_capture = False

    _container.processing_service.trigger_action("collage", 0)

    assert _container.processing_service._workflow_jobmodel is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._workflow_jobmodel is None

    phase2_item = _container.mediacollection_service.get_item_latest()
    assert phase2_item.unprocessed.suffix.lower() == ".jpg"

    with Image.open(phase2_item.unprocessed, formats=["JPEG"]) as img:
        img.verify()


def test_collage_manual_approval(_container: Container):
    before_count = _container.mediacollection_service.count()
    correct_after_count = before_count + 3  # there are 2 captures plus final collage, one image is rejected, that shall be deleted again

    appconfig.actions.collage[0].jobcontrol.ask_approval_each_capture = True

    # starts in separate thread
    _container.processing_service.trigger_action("collage", 0)

    # observer that is used to confirm the captures.
    assert _container.processing_service._workflow_jobmodel is not None  # statemachine was created after trigger_action
    wait_for_user_input_requested()
    _container.processing_service.continue_process()
    wait_for_user_input_requested()
    _container.processing_service.reject_capture()
    wait_for_user_input_requested()
    _container.processing_service.continue_process()

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._workflow_jobmodel is None

    assert correct_after_count == _container.mediacollection_service.count()


def test_collage_manual_abort(_container: Container):
    before_count = _container.mediacollection_service.count()
    correct_after_count = before_count  # there is one capture made but then abort. should have 0 items added

    appconfig.actions.collage[0].jobcontrol.ask_approval_each_capture = True

    _container.processing_service.trigger_action("collage", 0)

    assert _container.processing_service._workflow_jobmodel is not None

    wait_for_user_input_requested()
    _container.processing_service.continue_process()
    wait_for_user_input_requested()
    _container.processing_service.reject_capture()
    wait_for_user_input_requested()
    _container.processing_service.abort_process()

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._workflow_jobmodel is None

    assert correct_after_count == _container.mediacollection_service.count()


def test_animation(_container: Container):
    _container.processing_service.trigger_action("animation", 0)

    assert _container.processing_service._workflow_jobmodel is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._workflow_jobmodel is None

    phase2_item = _container.mediacollection_service.get_item_latest()
    assert phase2_item.unprocessed.suffix.lower() == ".gif"

    with Image.open(phase2_item.unprocessed, formats=["GIF"]) as img:
        img.verify()


def test_video(_container: Container):
    _container.processing_service.trigger_action("video", 0)

    assert _container.processing_service._workflow_jobmodel is not None
    number_of_images_before = _container.mediacollection_service.count()

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._workflow_jobmodel is None

    assert _container.mediacollection_service.count() == number_of_images_before + 1

    video_item = _container.mediacollection_service.get_item_latest()
    assert video_item.unprocessed.suffix.lower() == ".mp4"

    # boomerang reverses video so double length
    desired_video_duration = appconfig.actions.video[0].processing.video_duration
    out_dur = video_duration(video_item.unprocessed)
    if appconfig.actions.video[0].processing.boomerang:
        desired_video_duration *= 2
        desired_video_duration /= appconfig.actions.video[0].processing.boomerang_speed

    # ensure written video is about in tolerance duration
    assert out_dur == pytest.approx(desired_video_duration, abs=0.5)


def test_video_stop_early(_container: Container):
    _container.processing_service.trigger_action("video", 0)

    assert _container.processing_service._workflow_jobmodel is not None
    number_of_images_before = _container.mediacollection_service.count()

    # wait until actually recording
    timeout_counter = 0
    while not _container.aquisition_service.is_recording():
        time.sleep(0.05)
        timeout_counter += 0.05
        if timeout_counter > 10:
            raise RuntimeError("timed out waiting for record to start!")

    # recording active, wait 1 secs before stopping.
    desired_video_duration = 1
    time.sleep(desired_video_duration)
    _container.processing_service.continue_process()
    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._workflow_jobmodel is None

    assert _container.mediacollection_service.count() == number_of_images_before + 1

    video_item = _container.mediacollection_service.get_item_latest()
    assert video_item.unprocessed.suffix.lower() == ".mp4"

    # ensure written video is about in tolerance duration
    video_duration_seconds = abs(round(video_duration(video_item.unprocessed), 1))
    logger.info(f"{video_duration_seconds=}")

    # boomerang reverses video so double length
    if appconfig.actions.video[0].processing.boomerang:
        desired_video_duration *= 2
        desired_video_duration /= appconfig.actions.video[0].processing.boomerang_speed
    assert video_duration_seconds == pytest.approx(desired_video_duration, abs=0.5)


def test_multicamera(_container: Container):
    number_of_images_before = _container.mediacollection_service.count()

    _container.processing_service.trigger_action("multicamera", 0)

    assert _container.processing_service._workflow_jobmodel is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._workflow_jobmodel is None

    assert _container.mediacollection_service.count() == number_of_images_before + 5

    phase2_item = _container.mediacollection_service.get_item_latest()
    assert phase2_item.unprocessed.suffix.lower() == ".gif"

    with Image.open(phase2_item.unprocessed, formats=["GIF"]) as img:
        img.verify()
