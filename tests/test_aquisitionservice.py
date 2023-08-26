import io
import logging

import pytest
from dependency_injector import providers
from PIL import Image
from pymitter import EventEmitter

from photobooth.appconfig import (
    AppConfig,
    EnumImageBackendsLive,
    EnumImageBackendsMain,
)
from photobooth.services.containers import ServicesContainer

logger = logging.getLogger(name=None)


# need fixture on module scope otherwise tests fail because GPIO lib gets messed up
@pytest.fixture()
def services() -> ServicesContainer:
    # setup
    evtbus = providers.Singleton(EventEmitter)
    config = providers.Singleton(AppConfig)
    services = ServicesContainer(
        evtbus=evtbus,
        config=config,
    )

    config().backends.LIVEPREVIEW_ENABLED = True
    config().backends.MAIN_BACKEND = EnumImageBackendsMain.SIMULATED
    config().backends.LIVE_BACKEND = EnumImageBackendsLive.SIMULATED

    services.init_resources()
    yield services
    services.shutdown_resources()


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
    services.config().backends.LIVE_BACKEND = EnumImageBackendsLive.DISABLED
    # shutdown/init to restart resources
    services.shutdown_resources()
    services.init_resources()

    # not clear yet, why need to get service again to get pics.
    aquisition_service = services.aquisition_service()

    # now main and secondary provide images
    with Image.open(io.BytesIO(aquisition_service.primary_backend.wait_for_hq_image())) as img:
        logger.info(img)
        img.verify()

    # secondary fails, because disabled
    with pytest.raises(AttributeError):
        aquisition_service.secondary_backend.wait_for_hq_image()
