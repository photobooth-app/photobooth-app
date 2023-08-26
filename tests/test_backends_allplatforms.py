"""
Testing Simulated Backend
"""
import logging

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from pymitter import EventEmitter

from photobooth.appconfig import AppConfig
from photobooth.application import app
from photobooth.services.backends.containers import BackendsContainer

from .backends_utils import get_images

logger = logging.getLogger(name=None)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        yield client
        # client.app.container.services.aquisition_service()._backends.shutdown_resources()
        client.app.container.shutdown_resources()


def test_backends_same_instance(client: TestClient):
    return
    sim_backend1 = BackendsContainer(
        evtbus=providers.Singleton(EventEmitter),
        config=providers.Singleton(AppConfig),
    ).simulated_backend()

    sim_backend2 = client.app.container.backends().simulated_backend()

    logger.info(sim_backend1)
    logger.info(sim_backend2)

    assert sim_backend1 is sim_backend2


def test_get_images_simulated():
    backend = BackendsContainer(evtbus=providers.Singleton(EventEmitter), config=providers.Singleton(AppConfig))
    simulated_backend = backend.simulated_backend()

    """get lores and hires images from backend and assert"""
    get_images(simulated_backend)


def test_get_images_webcamcv2():
    backend = BackendsContainer(evtbus=providers.Singleton(EventEmitter), config=providers.Singleton(AppConfig))

    from photobooth.services.backends.webcamcv2 import available_camera_indexes

    logger.info("probing for available cameras")
    _availableCameraIndexes = available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    cameraIndex = _availableCameraIndexes[0]

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    logger.info(f"using first camera index to test: {cameraIndex}")
    backend.config().backends.cv2_device_index = cameraIndex

    """get lores and hires images from backend and assert"""

    webcamcv2_backend = backend.webcamcv2_backend()
    get_images(webcamcv2_backend)
