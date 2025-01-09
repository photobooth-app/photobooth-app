import logging

import pytest

from photobooth.container import Container, container

logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Container:
    container.start()
    yield container
    container.stop()


def test_ensure_scaled_repr_created(_container: Container):
    pass
    # TODO: rewrite tests for mediacollection.
