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
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA

    container.start()

    # deliver
    yield container
    container.stop()


def test_getimages_frommultiple_backends(_container: Container):
    with Image.open(io.BytesIO(_container.aquisition_service.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()


def test_getimages_directlyaccess_backends(_container: Container):
    with Image.open(io.BytesIO(_container.aquisition_service._main_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(_container.aquisition_service._main_backend._wait_for_lores_image())) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(_container.aquisition_service._live_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(_container.aquisition_service._live_backend._wait_for_lores_image())) as img:
        logger.info(img)
        img.verify()


def test_getimages_change_backend_during_runtime(_container: Container):
    # main gives image
    with Image.open(io.BytesIO(_container.aquisition_service._main_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    # secondary
    with Image.open(io.BytesIO(_container.aquisition_service._live_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    # now reconfigure
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.DISABLED

    # shutdown/init to restart resources
    _container.aquisition_service.stop()
    _container.aquisition_service.start()

    # now main and secondary provide images
    with Image.open(io.BytesIO(_container.aquisition_service._main_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    # secondary fails, because disabled
    with pytest.raises(RuntimeError):
        _container.aquisition_service._live_backend.wait_for_hq_image()


def test_nobackend_available_for_hq(_container: Container):
    # now reconfigure
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.DISABLED
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.DISABLED
    _container.aquisition_service.stop()
    _container.aquisition_service.start()

    with pytest.raises(RuntimeError):
        _container.aquisition_service.wait_for_hq_image()


def test_gen_stream(_container: Container):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.DISABLED
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.DISABLED
    _container.aquisition_service.stop()
    _container.aquisition_service.start()

    with pytest.raises(RuntimeError):
        _container.aquisition_service.gen_stream()


def test_gen_stream_main_backend(_container: Container):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.DISABLED
    _container.aquisition_service.stop()
    _container.aquisition_service.start()

    assert _container.aquisition_service.gen_stream()
    assert _container.aquisition_service._main_backend.gen_stream()
    assert not _container.aquisition_service._is_real_backend(_container.aquisition_service._live_backend)


def test_gen_stream_live_backend(_container: Container):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.DISABLED
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA
    _container.aquisition_service.stop()
    _container.aquisition_service.start()

    assert _container.aquisition_service.gen_stream()
    assert not _container.aquisition_service._is_real_backend(_container.aquisition_service._main_backend)
    assert _container.aquisition_service._live_backend.gen_stream()


def test_get_stats(_container: Container):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA
    _container.aquisition_service.stop()
    _container.aquisition_service.start()

    logger.info(_container.aquisition_service.stats())


def test_simulated_init_exceptions(_container: Container):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "__init__", error_mock):
        try:
            _: AquisitionService = AquisitionService(SseService())
        except Exception as exc:
            raise AssertionError(f"'VirtualCameraBackend' raised an exception, but it should fail in silence {exc}") from exc


def test_simulated_start_exceptions(_container: Container):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "start", error_mock):
        try:
            aq: AquisitionService = AquisitionService(SseService())
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
            aq: AquisitionService = AquisitionService(SseService())
            aq.stop()

        except Exception as exc:
            raise AssertionError(f"'VirtualCameraBackend' raised an exception, but it should fail in silence {exc}") from exc
