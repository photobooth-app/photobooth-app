import logging
import os

import pytest

from photobooth.containers import ApplicationContainer
from photobooth.services.containers import ServicesContainer
from photobooth.services.processing.jobmodels import JobModelBase

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def services() -> ServicesContainer:
    # setup
    application_container = ApplicationContainer()

    services = application_container.services()

    # create one image to ensure there is at least one
    services.processing_service().start(JobModelBase.Typ.image, 1)

    # deliver
    yield services
    services.shutdown_resources()


def test_ensure_scaled_repr_created(services: ServicesContainer):
    """this function processes single images (in contrast to collages or videos)"""

    # get the newest image id
    mediaitem = services.mediacollection_service().db_get_images()[0]

    # should just run without any exceptions.
    try:
        mediaitem.ensure_scaled_repr_created()
    except Exception as exc:
        raise AssertionError(f"'ensure_scaled_repr_created' raised an exception :( {exc}") from exc


def test_ensure_scaled_repr_created_processed(services: ServicesContainer):
    """this function processes single images (in contrast to collages or videos)"""

    # get the newest image id
    mediaitem = services.mediacollection_service().db_get_images()[0]

    os.remove(mediaitem.path_full)
    os.remove(mediaitem.path_preview)
    os.remove(mediaitem.path_thumbnail)
    os.remove(mediaitem.path_full_unprocessed)
    os.remove(mediaitem.path_preview_unprocessed)
    os.remove(mediaitem.path_thumbnail_unprocessed)

    # should just run without any exceptions.
    try:
        mediaitem.ensure_scaled_repr_created()
    except Exception as exc:
        raise AssertionError(f"'ensure_scaled_repr_created' raised an exception :( {exc}") from exc

    assert os.path.isfile(mediaitem.path_full)
    assert os.path.isfile(mediaitem.path_preview)
    assert os.path.isfile(mediaitem.path_thumbnail)
    assert os.path.isfile(mediaitem.path_full_unprocessed)
    assert os.path.isfile(mediaitem.path_preview_unprocessed)
    assert os.path.isfile(mediaitem.path_thumbnail_unprocessed)
