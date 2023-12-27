import io
import logging
from importlib import reload
from unittest import mock
from unittest.mock import patch

import pytest
from PIL import Image

import photobooth.services.config
from photobooth.containers import ApplicationContainer
from photobooth.services.aquisitionservice import AquisitionService
from photobooth.services.config import appconfig
from photobooth.services.config.groups.backends import (
    EnumImageBackendsLive,
    EnumImageBackendsMain,
)
from photobooth.services.containers import ServicesContainer

reload(photobooth.services.config)  # reset config to defaults.
logger = logging.getLogger(name=None)


@pytest.fixture(scope="function")
def services() -> ServicesContainer:
    # setup

    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsMain.VIRTUALCAMERA
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA

    application_container = ApplicationContainer()

    # application_container.services().init_resources()

    # deliver
    yield application_container.services()
    application_container.shutdown_resources()


def test_getimages_frommultiple_backends(services: ServicesContainer):
    aquisition_service: AquisitionService = services.aquisition_service()
    # is started automatically now: aquisition_service.start()

    with Image.open(io.BytesIO(aquisition_service.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()


def test_getimages_directlyaccess_backends(services: ServicesContainer):
    aquisition_service: AquisitionService = services.aquisition_service()

    with Image.open(io.BytesIO(aquisition_service._main_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(aquisition_service._main_backend._wait_for_lores_image())) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(aquisition_service._live_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(aquisition_service._live_backend._wait_for_lores_image())) as img:
        logger.info(img)
        img.verify()


def test_getimages_change_backend_during_runtime(services: ServicesContainer):
    aquisition_service: AquisitionService = services.aquisition_service()

    # main gives image
    with Image.open(io.BytesIO(aquisition_service._main_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    # secondary
    with Image.open(io.BytesIO(aquisition_service._live_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    # now reconfigure
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.DISABLED
    # shutdown/init to restart resources
    services.shutdown_resources()
    # services.init_resources(), init is automatic if needed.

    # not clear yet, why need to get service again to get pics.
    aquisition_service = services.aquisition_service()

    # now main and secondary provide images
    with Image.open(io.BytesIO(aquisition_service._main_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    # secondary fails, because disabled
    with pytest.raises(RuntimeError):
        aquisition_service._live_backend.wait_for_hq_image()


def test_nobackend_available_for_hq(services: ServicesContainer):
    # now reconfigure
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.DISABLED
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.DISABLED

    aquisition_service: AquisitionService = services.aquisition_service()

    with pytest.raises(RuntimeError):
        aquisition_service.wait_for_hq_image()


def test_gen_stream(services: ServicesContainer):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.DISABLED
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.DISABLED

    aquisition_service: AquisitionService = services.aquisition_service()

    with pytest.raises(RuntimeError):
        aquisition_service.gen_stream()


def test_gen_stream_main_backend(services: ServicesContainer):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.DISABLED

    aquisition_service: AquisitionService = services.aquisition_service()

    assert aquisition_service.gen_stream()
    assert aquisition_service._main_backend.gen_stream()
    assert not aquisition_service._is_real_backend(aquisition_service._live_backend)


def test_gen_stream_live_backend(services: ServicesContainer):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.DISABLED
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA

    aquisition_service: AquisitionService = services.aquisition_service()

    assert aquisition_service.gen_stream()
    assert not aquisition_service._is_real_backend(aquisition_service._main_backend)
    assert aquisition_service._live_backend.gen_stream()


def test_get_stats(services: ServicesContainer):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA

    aquisition_service: AquisitionService = services.aquisition_service()

    logger.info(aquisition_service.stats())


def test_simulated_init_exceptions(services: ServicesContainer):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "__init__", error_mock):
        try:
            _: AquisitionService = services.aquisition_service()
        except Exception as exc:
            raise AssertionError(f"'VirtualCameraBackend' raised an exception, but it should fail in silence {exc}") from exc


def test_simulated_start_exceptions(services: ServicesContainer):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "start", error_mock):
        try:
            aq: AquisitionService = services.aquisition_service()
            aq.start()

        except Exception as exc:
            raise AssertionError(f"'VirtualCameraBackend' raised an exception, but it should fail in silence {exc}") from exc


def test_simulated_stop_exceptions(services: ServicesContainer):
    # test to ensure a failing backend doesnt break the whole system due to uncatched exceptions
    from photobooth.services.backends.virtualcamera import VirtualCameraBackend

    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception("mock error")

    with patch.object(VirtualCameraBackend, "stop", error_mock):
        try:
            aq: AquisitionService = services.aquisition_service()
            aq.stop()

        except Exception as exc:
            raise AssertionError(f"'VirtualCameraBackend' raised an exception, but it should fail in silence {exc}") from exc
