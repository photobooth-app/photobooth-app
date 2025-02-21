import logging
import time
from collections.abc import Generator
from multiprocessing import Process

import pytest
import uvicorn
from pydantic import HttpUrl
from wigglecam import __main__
from wigglecam.container import Container

from photobooth.services.backends.wigglecam import WigglecamBackend
from photobooth.services.config.groups.backends import ConfigCameraNode, GroupBackendWigglecam

from ..util import get_images

logger = logging.getLogger(name=None)


def run_server():
    uvicorn.run(__main__.app, host="127.0.0.1", port=8081)


@pytest.fixture(scope="module")
def emulated_node() -> Generator[Container, None, None]:
    proc = Process(target=run_server, args=(), daemon=True)
    proc.start()
    time.sleep(2)  # need to wait until virtual node is actually available. TODO: could improve by actually checking.
    yield __main__.container
    proc.kill()  # Cleanup after test


@pytest.fixture()
def backend_wigglecam() -> Generator[WigglecamBackend, None, None]:
    backend = WigglecamBackend(
        GroupBackendWigglecam(
            nodes=[ConfigCameraNode(description="test", base_url=HttpUrl("http://127.0.0.1:8081"))],
        )
    )

    backend.start()
    backend.block_until_device_is_running()
    yield backend
    backend.stop()


def test_service_reload(backend_wigglecam):
    """container reloading works reliable"""

    for _ in range(1, 5):
        backend_wigglecam.start()
        backend_wigglecam.stop()


def test_assert_is_alive(emulated_node, backend_wigglecam):
    assert backend_wigglecam._device_alive()


def test_optimize_mode(backend_wigglecam):
    backend_wigglecam._on_configure_optimized_for_hq_capture()
    backend_wigglecam._on_configure_optimized_for_hq_preview()
    backend_wigglecam._on_configure_optimized_for_idle()


def test_read_still(emulated_node, backend_wigglecam):
    get_images(backend_wigglecam)
