import logging

import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory

from photobooth.appconfig import appconfig
from photobooth.container import container
from photobooth.database.database import create_db_and_tables

logger = logging.getLogger(name=None)

# globally set device pin_factory to mock
Device.pin_factory = MockFactory()


@pytest.fixture(scope="function", autouse=True)
def global_function_setup1():
    logger.info("global function-scoped mediaitem setup")

    if container.mediacollection_service.count() == 0:
        logger.info("no mediaitem in collection, creating one image")
        container.start()
        if container.mediacollection_service.count() == 0:
            container.processing_service.trigger_action("image", 0)
            container.processing_service.wait_until_job_finished()
        container.stop()

    yield


@pytest.fixture(scope="function", autouse=True)
def global_function_setup2():
    logger.info("global function-scoped appconfig reset and optimization for speed reasons")

    appconfig.reset_defaults()

    appconfig.actions.image[0].jobcontrol.countdown_capture = 0.2
    appconfig.actions.collage[0].jobcontrol.countdown_capture = 0.2
    appconfig.actions.collage[0].jobcontrol.countdown_capture_second_following = 0.2
    appconfig.actions.collage[0].jobcontrol.approve_autoconfirm_timeout = 0.5
    appconfig.actions.animation[0].jobcontrol.countdown_capture = 0.2
    appconfig.actions.animation[0].jobcontrol.countdown_capture_second_following = 0.2
    appconfig.actions.animation[0].jobcontrol.approve_autoconfirm_timeout = 0.5
    appconfig.actions.video[0].jobcontrol.countdown_capture = 0.2

    yield


@pytest.fixture(scope="session", autouse=True)
def session_setup1():
    create_db_and_tables()

    yield
