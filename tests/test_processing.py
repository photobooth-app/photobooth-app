import logging

import pytest
import statemachine.exceptions

from photobooth.container import Container, container
from photobooth.services.config import appconfig

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
    container.processing_service.start_job_1pic()

    # deliver
    yield container
    container.stop()


def test_capture(_container: Container):
    """this function processes single images (in contrast to collages or videos)"""
    appconfig.common.collage_automatic_capture_continue = False

    _container.processing_service.start_job_1pic()

    assert _container.processing_service.idle.is_active


def test_capture_autoconfirm(_container: Container):
    """this function processes single images (in contrast to collages or videos)"""
    appconfig.common.collage_automatic_capture_continue = True

    _container.processing_service.start_job_1pic()

    assert _container.processing_service.idle.is_active


def test_capture_zero_countdown(_container: Container):
    """this function processes single images (in contrast to collages or videos)"""
    appconfig.common.countdown_capture_first = 0

    _container.processing_service.start_job_1pic()

    assert _container.processing_service.idle.is_active


def test_capture_manual_confirm(_container: Container):
    # there is not confirm/reject for single captures possible
    pass


def test_simple_capture_illegal_jobs(_container: Container):
    """this function processes single images (in contrast to collages or videos)"""

    _container.processing_service.start_job_1pic()
    with pytest.raises(statemachine.exceptions.TransitionNotAllowed):
        _container.processing_service.confirm_capture()

    assert _container.processing_service.idle.is_active


def test_collage(_container: Container):
    appconfig.common.collage_automatic_capture_continue = False

    _container.processing_service.start_job_collage()

    assert _container.processing_service.idle.is_active is False

    while not _container.processing_service.job_finished():
        _container.processing_service.confirm_capture()

    assert _container.processing_service.idle.is_active


def test_collage_autoconfirm(_container: Container):
    appconfig.common.collage_automatic_capture_continue = True

    _container.processing_service.start_job_collage()

    assert _container.processing_service.idle.is_active


def test_collage_manual_confirm(_container: Container):
    appconfig.common.collage_automatic_capture_continue = False

    _container.processing_service.start_job_collage()

    assert not _container.processing_service.idle.is_active

    while not _container.processing_service.job_finished():
        _container.processing_service.confirm_capture()

    assert _container.processing_service.idle.is_active


def test_collage_manual_reject(_container: Container):
    appconfig.common.collage_automatic_capture_continue = False

    _container.processing_service.start_job_collage()

    assert not _container.processing_service.idle.is_active

    _container.processing_service.reject_capture()
    # TODO: need to ensure database is updated properly!

    while not _container.processing_service.job_finished():
        _container.processing_service.confirm_capture()

    assert _container.processing_service.idle.is_active


def test_collage_manual_abort(_container: Container):
    appconfig.common.collage_automatic_capture_continue = False

    _container.processing_service.start_job_collage()

    assert not _container.processing_service.idle.is_active

    _container.processing_service.abort_process()
    # TODO: need to ensure database is updated properly!

    assert _container.processing_service.idle.is_active
