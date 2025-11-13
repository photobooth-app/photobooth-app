import logging
import subprocess
import sys

import pytest

from photobooth.services.backends.wigglecam import GroupCameraWigglecam, WigglecamBackend
from photobooth.services.config.groups.cameras import WigglecamNodes
from tests.tests.util import block_until_device_is_running, get_images

logger = logging.getLogger(name=None)


@pytest.fixture
def wiggle_node_proc():
    proc = subprocess.Popen([sys.executable, "-m", "wigglecam", "--device-id", "0", "--base-port", "5560"])
    yield proc
    proc.terminate()
    proc.wait()


@pytest.fixture()
def backend_wigglecam():
    # setup
    backend = WigglecamBackend(GroupCameraWigglecam(devices=[WigglecamNodes(description="wigglenodes", address="127.0.0.1", base_port=5560)]))

    # deliver
    backend.start()
    block_until_device_is_running(backend)

    yield backend
    backend.stop()


# @pytest.mark.asyncio
def test_virtual_camera_capture(wiggle_node_proc, backend_wigglecam):
    get_images(backend_wigglecam)
