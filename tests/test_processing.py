import logging

import pytest
import statemachine.exceptions

from photobooth.containers import ApplicationContainer
from photobooth.services.containers import ServicesContainer
from photobooth.services.processing.jobmodels import JobModelBase

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

    services.processing_service().start(JobModelBase.Typ.image, 1)
    # services.processing_service().capture_next()

    assert services.processing_service().idle.is_active


def test_simple_capture_illegal_jobs(services: ServicesContainer):
    """this function processes single images (in contrast to collages or videos)"""

    # TODO: should raise an error
    services.processing_service().start(JobModelBase.Typ.image, 1)
    with pytest.raises(statemachine.exceptions.TransitionNotAllowed):
        services.processing_service().capture_next()

    assert services.processing_service().idle.is_active


def test_collage(services: ServicesContainer):
    services.processing_service().start(
        JobModelBase.Typ.collage, services.mediaprocessing_service().number_of_captures_to_take_for_collage()
    )
    while services.processing_service().capture.is_active:
        services.processing_service().capture_next()

    assert services.processing_service().idle.is_active


def test_collage_manual_continue(services: ServicesContainer):
    """this function processes single images (in contrast to collages or videos)"""

    services.mediaprocessing_service()
