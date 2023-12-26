import logging

import pytest
import statemachine.exceptions

from photobooth.containers import ApplicationContainer
from photobooth.services.config import appconfig
from photobooth.services.containers import ServicesContainer

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def services() -> ServicesContainer:
    # setup
    application_container = ApplicationContainer()

    services = application_container.services()

    # deliver
    yield services
    services.shutdown_resources()


def test_capture(services: ServicesContainer):
    """this function processes single images (in contrast to collages or videos)"""
    appconfig.common.collage_automatic_capture_continue = False

    services.processing_service().start_job_1pic()

    assert services.processing_service().idle.is_active


def test_capture_autoconfirm(services: ServicesContainer):
    """this function processes single images (in contrast to collages or videos)"""
    appconfig.common.collage_automatic_capture_continue = True

    services.processing_service().start_job_1pic()

    assert services.processing_service().idle.is_active


def test_capture_zero_countdown(services: ServicesContainer):
    """this function processes single images (in contrast to collages or videos)"""
    appconfig.common.countdown_capture_first = 0

    services.processing_service().start_job_1pic()

    assert services.processing_service().idle.is_active


def test_capture_manual_confirm(services: ServicesContainer):
    # there is not confirm/reject for single captures possible
    pass


def test_simple_capture_illegal_jobs(services: ServicesContainer):
    """this function processes single images (in contrast to collages or videos)"""

    services.processing_service().start_job_1pic()
    with pytest.raises(statemachine.exceptions.TransitionNotAllowed):
        services.processing_service().confirm_capture()

    assert services.processing_service().idle.is_active


def test_collage(services: ServicesContainer):
    appconfig.common.collage_automatic_capture_continue = False

    services.processing_service().start_job_collage()

    assert services.processing_service().idle.is_active is False

    while not services.processing_service().job_finished():
        services.processing_service().confirm_capture()

    assert services.processing_service().idle.is_active


def test_collage_autoconfirm(services: ServicesContainer):
    appconfig.common.collage_automatic_capture_continue = True

    services.processing_service().start_job_collage()

    assert services.processing_service().idle.is_active


def test_collage_manual_confirm(services: ServicesContainer):
    appconfig.common.collage_automatic_capture_continue = False

    services.processing_service().start_job_collage()

    assert not services.processing_service().idle.is_active

    while not services.processing_service().job_finished():
        services.processing_service().confirm_capture()

    assert services.processing_service().idle.is_active


def test_collage_manual_reject(services: ServicesContainer):
    appconfig.common.collage_automatic_capture_continue = False

    services.processing_service().start_job_collage()

    assert not services.processing_service().idle.is_active

    services.processing_service().reject_capture()
    # TODO: need to ensure database is updated properly!

    while not services.processing_service().job_finished():
        services.processing_service().confirm_capture()

    assert services.processing_service().idle.is_active


def test_collage_manual_abort(services: ServicesContainer):
    appconfig.common.collage_automatic_capture_continue = False

    services.processing_service().start_job_collage()

    assert not services.processing_service().idle.is_active

    services.processing_service().abort_process()
    # TODO: need to ensure database is updated properly!

    assert services.processing_service().idle.is_active
