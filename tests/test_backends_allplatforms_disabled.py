"""
Testing VIRTUALCAMERA Backend
"""
import logging

import pytest

from photobooth.services.backends.disabled import DisabledBackend
from photobooth.services.config import appconfig

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


@pytest.fixture()
def backend_disabled() -> DisabledBackend:
    # setup
    backend = DisabledBackend()

    # deliver
    backend.start()
    yield backend
    backend.stop()


def test_get_images_disabled(backend_disabled: DisabledBackend):
    """get lores and hires images from backend and assert"""

    with pytest.raises(RuntimeError):
        backend_disabled.wait_for_lores_image()

    with pytest.raises(RuntimeError):
        backend_disabled._wait_for_lores_image()

    with pytest.raises(RuntimeError):
        backend_disabled.wait_for_hq_image()
