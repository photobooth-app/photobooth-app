import io
import logging

import pytest
from PIL import Image

from photobooth.appconfig import (
    EnumImageBackendsLive,
    EnumImageBackendsMain,
)
from photobooth.containers import ApplicationContainer
from photobooth.services.containers import ServicesContainer

logger = logging.getLogger(name=None)


@pytest.fixture()
def services() -> ServicesContainer:
    # setup
    application_container = ApplicationContainer()

    # application_container.services().init_resources()

    application_container.config().backends.LIVEPREVIEW_ENABLED = True
    application_container.config().backends.MAIN_BACKEND = EnumImageBackendsMain.SIMULATED
    application_container.config().backends.LIVE_BACKEND = EnumImageBackendsLive.SIMULATED

    # deliver
    yield application_container.services()
    application_container.services().shutdown_resources()


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
