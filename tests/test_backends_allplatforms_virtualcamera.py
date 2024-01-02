"""
Testing VIRTUALCAMERA Backend
"""
import logging

import pytest

from photobooth.services.backends.virtualcamera import VirtualCameraBackend
from photobooth.services.config import appconfig

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


@pytest.fixture()
def backend_virtual() -> VirtualCameraBackend:
    # setup
    backend = VirtualCameraBackend()

    # deliver
    backend.start()
    yield backend
    backend.stop()
