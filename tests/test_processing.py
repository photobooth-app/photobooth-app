import logging

import pytest
import statemachine.exceptions

from photobooth.containers import ApplicationContainer
from photobooth.services.containers import ServicesContainer
from photobooth.services.processing.jobmodels import JobModel

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
    services.config().common.collage_automatic_capture_continue = False

    services.processing_service().start_job_1pic()

    assert services.processing_service().idle.is_active


def test_capture_autoconfirm(services: ServicesContainer):
    """this function processes single images (in contrast to collages or videos)"""
    services.config().common.collage_automatic_capture_continue = True

    services.processing_service().start_job_1pic()

    assert services.processing_service().idle.is_active


def test_simple_capture_illegal_jobs(services: ServicesContainer):
    """this function processes single images (in contrast to collages or videos)"""

    services.processing_service().start_job_1pic()
    with pytest.raises(statemachine.exceptions.TransitionNotAllowed):
        services.processing_service().confirm_capture()

    assert services.processing_service().idle.is_active


def test_collage(services: ServicesContainer):
    services.config().common.collage_automatic_capture_continue = False

    services.processing_service().start_job_collage()

    assert services.processing_service().idle.is_active is False

    while not services.processing_service().job_finished():
        services.processing_service().confirm_capture()

    assert services.processing_service().idle.is_active


def test_collage_autoconfirm(services: ServicesContainer):
    services.config().common.collage_automatic_capture_continue = True

    services.processing_service().start_job_collage()

    assert services.processing_service().idle.is_active
