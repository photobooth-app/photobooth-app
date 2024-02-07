import logging

import pytest

from photobooth.container import Container, container
from photobooth.services.config import appconfig
from photobooth.services.processingservice import ProcessingService

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Container:
    # setup
    container.start()
    # create one image to ensure there is at least one
    if container.mediacollection_service.number_of_images == 0:
        container.processing_service.start_job_1pic()

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

    def on_enter_state(self, target, event):
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
    appconfig.common.collage_automatic_capture_continue = False

    _container.processing_service.start_job_1pic()

    assert _container.processing_service._state_machine is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None


def test_capture_autoconfirm(_container: Container):
    """this function processes single images (in contrast to collages or videos)"""
    appconfig.common.collage_automatic_capture_continue = True

    _container.processing_service.start_job_1pic()

    assert _container.processing_service._state_machine is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None


def test_capture_zero_countdown(_container: Container):
    """this function processes single images (in contrast to collages or videos)"""
    appconfig.common.countdown_capture_first = 0

    _container.processing_service.start_job_1pic()

    assert _container.processing_service._state_machine is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None


def test_capture_manual_confirm(_container: Container):
    # there is not confirm/reject for single captures possible
    pass


def test_collage_auto_approval(_container: Container):
    appconfig.common.collage_automatic_capture_continue = True

    _container.processing_service.start_job_collage()

    assert _container.processing_service._state_machine is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None


def test_collage_manual_approval(_container: Container):
    appconfig.common.collage_automatic_capture_continue = False

    # starts in separate thread
    _container.processing_service.start_job_collage()

    # observer that is used to confirm the captures.
    _container.processing_service._state_machine.add_observer(ConfirmRejectUserinputObserver(_container.processing_service))

    assert _container.processing_service._state_machine is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None


def test_collage_manual_abort(_container: Container):
    appconfig.common.collage_automatic_capture_continue = False

    _container.processing_service.start_job_collage()
    _container.processing_service._state_machine.add_observer(ConfirmRejectUserinputObserver(_container.processing_service, abortjob=True))

    assert _container.processing_service._state_machine is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None


def test_animation(_container: Container):
    _container.processing_service.start_job_animation()

    assert _container.processing_service._state_machine is not None

    _container.processing_service.wait_until_job_finished()

    assert _container.processing_service._state_machine is None
