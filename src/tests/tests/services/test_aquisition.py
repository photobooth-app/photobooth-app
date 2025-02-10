import io
import logging
import subprocess
import time
from collections.abc import Generator
from unittest import mock
from unittest.mock import patch

import pytest
from PIL import Image

from photobooth.container import Container, container
from photobooth.services.aquisition import AquisitionService

logger = logging.getLogger(name=None)


@pytest.fixture(scope="module")
def _container() -> Generator[Container, None, None]:
    container.start()
    yield container
    container.stop()


def test_getimage(_container: Container):
    with Image.open(_container.aquisition_service.wait_for_still_file()) as img:
        logger.info(img)
        img.verify()


def test_getimages_directlyaccess_backends(_container: Container):
    with Image.open(_container.aquisition_service._backends[0].wait_for_still_file()) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(_container.aquisition_service._backends[0].wait_for_lores_image())) as img:
        logger.info(img)
        img.verify()


def test_preload_ffmpeg():
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(subprocess, "run", error_mock):
        # no error is raised if load fails.
        AquisitionService._load_ffmpeg()


def test_get_multicam_files(_container: Container):
    for image in _container.aquisition_service.wait_for_multicam_files():
        with Image.open(image) as img:
            logger.info(img)
            img.verify()


def test_getvideo(_container: Container):
    """get video from service"""
    _container.aquisition_service.start_recording()
    time.sleep(2)
    _container.aquisition_service.stop_recording()

    videopath = _container.aquisition_service.get_recorded_video()
    logger.info(f"video stored to file {videopath}")
    assert videopath and videopath.is_file()


def test_simulated_init_exceptions(_container: Container):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "__init__", error_mock):
        try:
            _: AquisitionService = AquisitionService()
        except Exception as exc:
            raise AssertionError(f"'VirtualCameraBackend' raised an exception, but it should fail in silence {exc}") from exc


def test_simulated_start_exceptions(_container: Container):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "start", error_mock):
        try:
            aq: AquisitionService = AquisitionService()
            aq.start()

        except Exception as exc:
            raise AssertionError(f"'VirtualCameraBackend' raised an exception, but it should fail in silence {exc}") from exc


def test_simulated_stop_exceptions(_container: Container):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "stop", error_mock):
        try:
            aq: AquisitionService = AquisitionService()
            aq.stop()

        except Exception as exc:
            raise AssertionError(f"'VirtualCameraBackend' raised an exception, but it should fail in silence {exc}") from exc


def test_get_livestream_virtualcamera(_container: Container):
    error_mock_timeout = mock.MagicMock()
    error_mock_timeout.side_effect = TimeoutError("backend time out simulated")

    error_mock_runtime = mock.MagicMock()
    error_mock_runtime.side_effect = RuntimeError("backend other exception simulated")

    g_stream = _container.aquisition_service.gen_stream()
    # stream is from second backend (live)

    i = 0
    for frame in g_stream:  # frame is bytes
        i = i + 1
        frame: bytes

        # ensure we always receive a valid jpeg frame, nothing else.
        # in case the backend failed, we receive a substitute image
        assert frame.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8\xff")

        if i == 5:
            # trigger virtual camera to send fault flag - this should result in supervisor stopping device, restart and continue deliver
            _container.aquisition_service._get_video_backend().is_marked_faulty.set()

        if i >= 30:
            g_stream.close()


def test_get_substitute_image(_container: Container):
    with Image.open(io.BytesIO(_container.aquisition_service._substitute_image("Error", "Something happened!", mirror=False))) as img:
        img.verify()
    with Image.open(io.BytesIO(_container.aquisition_service._substitute_image("Error", "Something happened!", mirror=True))) as img:
        img.verify()
