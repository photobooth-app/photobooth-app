import io
import logging
import time
from collections.abc import Generator
from multiprocessing import Process

import pytest
import uvicorn
from PIL import Image
from wigglecam import __main__
from wigglecam.connector import CameraNode
from wigglecam.connector.models import ConfigCameraNode

logger = logging.getLogger(name=None)


def run_server():
    uvicorn.run(__main__.app, host="127.0.0.1", port=8081)


@pytest.fixture(scope="module")
def emulated_node() -> Generator[CameraNode, None, None]:
    proc = Process(target=run_server, args=(), daemon=True)
    proc.start()

    node = CameraNode(ConfigCameraNode(description="test", base_url="http://127.0.0.1:8081"))
    while not node.can_connect:
        logger.debug("waiting until emulated server up and running")
        time.sleep(0.4)

    yield node
    proc.kill()  # Cleanup after test


def test_read_still(emulated_node):
    try:
        with Image.open(io.BytesIO(emulated_node.camera_still())) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes, {exc}") from exc
