import logging
from collections.abc import Generator
from multiprocessing import Process

import pytest
import uvicorn
from wigglecam import __main__
from wigglecam.container import Container

from photobooth.services.backends.wigglecam import WigglecamBackend
from photobooth.services.config.groups.backends import ConfigCameraNode, GroupBackendWigglecam

from .utils import get_images

logger = logging.getLogger(name=None)


def run_server():
    uvicorn.run(__main__.app, host="127.0.0.1", port=8081)


@pytest.fixture(scope="module")
def emulated_node() -> Generator[Container, None, None]:
    proc = Process(target=run_server, args=(), daemon=True)
    proc.start()
    yield __main__.container
    proc.kill()  # Cleanup after test


@pytest.fixture()
def backend_wigglecam() -> Generator[WigglecamBackend, None, None]:
    backend = WigglecamBackend(
        GroupBackendWigglecam(
            nodes=[ConfigCameraNode(description="test", base_url="http://127.0.0.1:8081")],
        )
    )

    backend.start()
    backend.block_until_device_is_running()
    yield backend
    backend.stop()


def test_read_still(emulated_node, backend_wigglecam):
    get_images(backend_wigglecam)
