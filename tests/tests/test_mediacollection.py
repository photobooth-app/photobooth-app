import logging

import pytest

from photobooth.container import Container, container
from photobooth.services.mediacollectionservice import MediaItem

logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Container:
    container.start()
    yield container
    container.stop()


def test_ensure_scaled_repr_created(_container: Container):
    """this function processes single images (in contrast to collages or videos)"""

    # get the newest image id
    mediaitem_from_collection = _container.mediacollection_service.db_get_most_recent_mediaitem()

    # create new instance and check against old one that metadata is avail.
    mediaitem_new_instance = MediaItem(mediaitem_from_collection.filename, None)  # load metadata from disk for exisiting element.

    # should just run without any exceptions.
    assert mediaitem_new_instance._config == mediaitem_from_collection._config
