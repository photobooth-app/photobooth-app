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
    backend = WigglecamBackend(GroupCameraWigglecam(devices=[WigglecamNodes(description="wigglenodes", address="127.0.0.1", base_port=5560)]))

    backend.start()
    block_until_device_is_running(backend)
    yield backend
    backend.stop()


def test_virtual_camera_capture(wiggle_node_proc, backend_wigglecam: WigglecamBackend):
    get_images(backend_wigglecam)


# def test_calibration_check(wiggle_node_proc, backend_wigglecam: WigglecamBackend):
#     backend_wigglecam.__cal_util.identity_all(4, 100, 100)
#     backend_wigglecam.__cal_util.save_calibration_data(CALIBRATION_DATA_PATH)


def test_raises_illegal_indexes():  # backend_wigglecam: WigglecamBackend):
    backend = WigglecamBackend(GroupCameraWigglecam(devices=[]))
    with pytest.raises(RuntimeError):
        backend.setup_resource()

    backend = WigglecamBackend(GroupCameraWigglecam(devices=[WigglecamNodes()]))
    # with pytest.raises(RuntimeError):
    backend.setup_resource()

    backend = WigglecamBackend(GroupCameraWigglecam(devices=[WigglecamNodes()]))
    with pytest.raises(RuntimeError):
        backend._config.index_cam_stills = 1
        backend.setup_resource()

    backend = WigglecamBackend(GroupCameraWigglecam(devices=[WigglecamNodes()]))
    with pytest.raises(RuntimeError):
        backend._config.index_cam_video = 1
        backend.setup_resource()
