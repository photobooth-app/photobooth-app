"""
Testing VIRTUALCAMERA Backend
"""

import logging
from collections.abc import Generator

import pytest

from photobooth.services.backends.virtualcamera import VirtualCameraBackend
from photobooth.services.config.groups.cameras import GroupCameraVirtual

from ..util import block_until_device_is_running, get_images

logger = logging.getLogger(name=None)


@pytest.fixture()
def backend_virtual() -> Generator[VirtualCameraBackend, None, None]:
    # setup
    backend = VirtualCameraBackend(GroupCameraVirtual())

    # deliver
    backend.start()
    block_until_device_is_running(backend)
    yield backend
    backend.stop()


def test_service_reload(backend_virtual: VirtualCameraBackend):
    """container reloading works reliable"""

    backend_virtual.stop()
    backend_virtual.start()


def test_optimize_mode(backend_virtual: VirtualCameraBackend):
    backend_virtual._handle_switchmode_still_mode()
    backend_virtual._handle_switchmode_video_mode()
    backend_virtual._handle_switchmode_standby()


def test_get_images_virtualcamera(backend_virtual: VirtualCameraBackend):
    """get lores and hires images from backend and assert"""
    get_images(backend_virtual, multicam_is_error=True)


def test_get_images_virtualcamera_hires(backend_virtual: VirtualCameraBackend):
    backend_virtual._config.emulate_hires_static_still = True
    get_images(backend_virtual, multicam_is_error=True)
