import io
import logging

import pytest
from PIL import Image

from photobooth.containers import ApplicationContainer
from photobooth.services.aquisitionservice import AquisitionService
from photobooth.services.config import appconfig
from photobooth.services.config.appconfig import (
    EnumImageBackendsLive,
    EnumImageBackendsMain,
)
from photobooth.services.containers import ServicesContainer

logger = logging.getLogger(name=None)


@pytest.fixture(scope="function")
def services() -> ServicesContainer:
    # setup
    application_container = ApplicationContainer()

    # application_container.services().init_resources()

    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsMain.VIRTUALCAMERA
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA

    # deliver
    yield application_container.services()
    application_container.shutdown_resources()


def test_getimages_frommultiple_backends(services: ServicesContainer):
    aquisition_service = services.aquisition_service()
    # is started automatically now: aquisition_service.start()

    with Image.open(io.BytesIO(aquisition_service.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()


def test_getimages_directlyaccess_backends(services: ServicesContainer):
    aquisition_service = services.aquisition_service()

    with Image.open(io.BytesIO(aquisition_service.primary_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(aquisition_service.primary_backend._wait_for_lores_image())) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(aquisition_service.secondary_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    with Image.open(io.BytesIO(aquisition_service.secondary_backend._wait_for_lores_image())) as img:
        logger.info(img)
        img.verify()


def test_getimages_change_backend_during_runtime(services: ServicesContainer):
    aquisition_service = services.aquisition_service()

    # main gives image
    with Image.open(io.BytesIO(aquisition_service.primary_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    # secondary
    with Image.open(io.BytesIO(aquisition_service.secondary_backend.wait_for_hq_image())) as img:
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
    with Image.open(io.BytesIO(aquisition_service.primary_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    # secondary fails, because disabled
    with pytest.raises(AttributeError):
        aquisition_service.secondary_backend.wait_for_hq_image()


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
    assert aquisition_service.primary_backend.gen_stream()
    assert aquisition_service.secondary_backend is None


def test_gen_stream_live_backend(services: ServicesContainer):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.DISABLED
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA

    aquisition_service: AquisitionService = services.aquisition_service()

    assert aquisition_service.gen_stream()
    assert aquisition_service.primary_backend is None
    assert aquisition_service.secondary_backend.gen_stream()


def test_get_stats(services: ServicesContainer):
    # now reconfigure
    appconfig.backends.LIVEPREVIEW_ENABLED = True
    appconfig.backends.MAIN_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA
    appconfig.backends.LIVE_BACKEND = EnumImageBackendsLive.VIRTUALCAMERA

    aquisition_service: AquisitionService = services.aquisition_service()

    logger.info(aquisition_service.stats())
