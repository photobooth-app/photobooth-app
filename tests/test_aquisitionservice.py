import io
import logging
from unittest import mock
from unittest.mock import patch

import pytest
from PIL import Image

from photobooth.container import Container, container
from photobooth.services.aquisitionservice import AquisitionService
from photobooth.services.config import appconfig
from photobooth.services.config.groups.backends import (
    EnumImageBackendsLive,
    EnumImageBackendsMain,
)
from photobooth.services.sseservice import SseService
from photobooth.services.wledservice import WledService

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


@pytest.fixture(scope="function")
def _container() -> Container:
    # setup

    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsMain.VIRTUALCAMERA
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.DISABLED

    container.start()

    # deliver
    yield container
    container.stop()


def test_getimage(_container: Container):
    with Image.open(io.BytesIO(_container.aquisition_service.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()


def test_getimages_directlyaccess_backends(_container: Container):
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsMain.VIRTUALCAMERA
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA

    container.stop()
    container.start()

    with Image.open(io.BytesIO(_container.aquisition_service._main_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(_container.aquisition_service._main_backend.wait_for_lores_image())) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(_container.aquisition_service._live_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(_container.aquisition_service._live_backend.wait_for_lores_image())) as img:
        logger.info(img)
        img.verify()


def test_getimages_change_backend_during_runtime(_container: Container):
    # main gives image
    with Image.open(io.BytesIO(_container.aquisition_service._main_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    # secondary fails, because disabled
    assert _container.aquisition_service._live_backend is None

    # now reconfigure
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA

    # shutdown/init to restart resources
    _container.aquisition_service.stop()
    _container.aquisition_service.start()

    # now main and secondary provide images
    with Image.open(io.BytesIO(_container.aquisition_service._main_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    # secondary
    with Image.open(io.BytesIO(_container.aquisition_service._live_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()


def test_gen_stream_main_backend(_container: Container):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.DISABLED
    _container.aquisition_service.stop()
    _container.aquisition_service.start()

    assert _container.aquisition_service.gen_stream()
    assert not _container.aquisition_service._is_real_backend(_container.aquisition_service._live_backend)


def test_get_stats(_container: Container):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA
    _container.aquisition_service.stop()
    _container.aquisition_service.start()

    logger.info(_container.aquisition_service.stats())


def test_switch_modes(_container: Container):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA
    _container.aquisition_service.stop()
    _container.aquisition_service.start()

    _container.aquisition_service.switch_backends_to_capture_mode()
    _container.aquisition_service.switch_backends_to_preview_mode()


def test_simulated_init_exceptions(_container: Container):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "__init__", error_mock):
        try:
            _: AquisitionService = AquisitionService(SseService(), WledService(SseService()))
        except Exception as exc:
            raise AssertionError(f"'VirtualCameraBackend' raised an exception, but it should fail in silence {exc}") from exc


def test_simulated_start_exceptions(_container: Container):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "start", error_mock):
        try:
            aq: AquisitionService = AquisitionService(SseService(), WledService(SseService()))
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
            aq: AquisitionService = AquisitionService(SseService(), WledService(SseService()))
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
        frame: bytes

        # ensure we always receive a valid jpeg frame, nothing else.
        # in case the backend failed, we receive a substitute image
        assert frame.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8\xff")

        if i == 5:
            # trigger virtual camera to send fault flag - this should result in supervisor stopping device, restart and continue deliver
            logger.info("setting _device_set_status_fault_flag True")
            _container.aquisition_service._main_backend._device_set_status_fault_flag()

        if i == 10:
            # trigger virtual camera to send fault flag - this should result in supervisor stopping device, restart and continue deliver
            logger.info("setting _event_proc_shutdown True")
            _container.aquisition_service._main_backend._event_proc_shutdown.set()

        # following tests not working yet:
        # if i == 15:
        #     logger.info("simulating timeout exception mock")
        #     patch.object(_container.aquisition_service._main_backend, "wait_for_lores_image", error_mock_timeout)

        # if i == 20:
        #     logger.info("simulating runtime exception mock")
        #     patch.object(_container.aquisition_service._main_backend, "wait_for_lores_image", error_mock_runtime)

        if i > 30:
            g_stream.close()

        i = i + 1


def test_get_substitute_image(_container: Container):
    with Image.open(io.BytesIO(_container.aquisition_service._substitute_image("Error", "Something happened!", mirror=False))) as img:
        img.verify()
    with Image.open(io.BytesIO(_container.aquisition_service._substitute_image("Error", "Something happened!", mirror=True))) as img:
        img.verify()
