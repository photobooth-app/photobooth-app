"""
Testing Simulated Backend
"""
import io
import logging

import pytest
from PIL import Image
from pymitter import EventEmitter

from photobooth.appconfig import AppConfig
from photobooth.services.backends.abstractbackend import AbstractBackend
from photobooth.services.backends.containers import BackendsContainer

logger = logging.getLogger(name=None)


def get_images(backend: AbstractBackend):
    logger.info(f"testing backend {backend.__module__}")
    backend.start()

    try:
        with Image.open(
            io.BytesIO(
                backend._wait_for_lores_image()  # pylint:disable=protected-access
            )
        ) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(
            f"backend did not return valid image bytes, {exc}"
        ) from exc

    try:
        with Image.open(io.BytesIO(backend.wait_for_hq_image())) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(
            f"backend did not return valid image bytes, {exc}"
        ) from exc

    # stop backend, ensure process is joined properly to collect coverage:
    # https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html#if-you-use-multiprocessing-process
    backend.stop()


def test_get_images_simulated():
    backend = BackendsContainer(evtbus=EventEmitter(), settings=AppConfig())
    simulated_backend = backend.simulated_backend()

    """get lores and hires images from backend and assert"""
    get_images(simulated_backend)


def test_get_images_webcamcv2():
    backend = BackendsContainer(evtbus=EventEmitter(), settings=AppConfig())
    webcamcv2_backend = backend.webcamcv2_backend()
    from photobooth.services.backends.webcamcv2 import available_camera_indexes

    logger.info("probing for available cameras")
    _availableCameraIndexes = available_camera_indexes()
    if not _availableCameraIndexes:
        pytest.skip("no camera found, skipping test")

    cameraIndex = _availableCameraIndexes[0]

    logger.info(f"available camera indexes: {_availableCameraIndexes}")
    logger.info(f"using first camera index to test: {cameraIndex}")

    # modify config:
    BackendsContainer.config.backends.cv2_device_index.from_value(cameraIndex)
    # ApplicationContainer.settings().backends.cv2_device_index = cameraIndex

    """get lores and hires images from backend and assert"""
    get_images(webcamcv2_backend)
