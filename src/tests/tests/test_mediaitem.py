import logging
from collections.abc import Generator

import pytest

from photobooth.container import Container, container

logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture(scope="module")
def _container() -> Generator[Container, None, None]:
    container.start()
    yield container
    container.stop()


def test_ensure_scaled_repr_created(_container: Container):
    pass
    # TODO: need new tests.
