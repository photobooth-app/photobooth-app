"""
Testing VIRTUALCAMERA Backend
"""

import logging
import time
from collections.abc import Generator

import pytest

from photobooth.services.backends.virtualcamera import VirtualCameraBackend
from photobooth.services.config.groups.backends import GroupBackendVirtualcamera

from ..utils import get_images

logger = logging.getLogger(name=None)


@pytest.fixture()
def backend_virtual() -> Generator[VirtualCameraBackend, None, None]:
    # setup
    backend = VirtualCameraBackend(GroupBackendVirtualcamera())

    # deliver
    backend.start()
    backend.block_until_device_is_running()
    yield backend
    backend.stop()


def test_assert_is_alive(backend_virtual: VirtualCameraBackend):
    assert backend_virtual._device_alive()


def test_get_images_virtualcamera(backend_virtual: VirtualCameraBackend):
    """get lores and hires images from backend and assert"""
    get_images(backend_virtual)


def test_get_video_virtualcamera(backend_virtual: VirtualCameraBackend):
    """get lores and hires images from backend and assert"""
    backend_virtual.start_recording(video_framerate=5)
    time.sleep(2)
    backend_virtual.stop_recording()

    videopath = backend_virtual.get_recorded_video()
    logger.info(f"video stored to file {videopath}")
    assert videopath and videopath.is_file()
