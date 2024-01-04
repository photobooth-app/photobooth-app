"""
Testing VIRTUALCAMERA Backend
"""
import logging

import pytest

from photobooth.services.backends.virtualcamera import VirtualCameraBackend
from photobooth.services.config import appconfig

from .backends_utils import get_images

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
    backend.block_until_device_is_running()
    yield backend
    backend.stop()


def test_get_images_virtualcamera(backend_virtual: VirtualCameraBackend):
    """get lores and hires images from backend and assert"""
    get_images(backend_virtual)


def test_get_images_virtualcamera_force_processexit_ensure_flag_fault_set(backend_virtual: VirtualCameraBackend):
    """get lores and hires images from backend and assert"""
    get_images(backend_virtual)

    # force process to exit, which equals a device failing.
    backend_virtual._virtualcamera_process.terminate()

    get_images(backend_virtual)
