import logging

import pytest

from photobooth.container import container
from photobooth.services.config import appconfig

logger = logging.getLogger(name=None)


@pytest.fixture(scope="function", autouse=True)
def global_session_setup():
    logger.info("global function-scoped mediaitem setup")

    if container.mediacollection_service.number_of_images == 0:
        logger.info("no mediaitem in collection, creating one image")
        container.processing_service.trigger_action("image", 0)
        container.processing_service.wait_until_job_finished()

    yield


@pytest.fixture(scope="function", autouse=True)
def global_function_setup():
    logger.info("global function-scoped appconfig reset and optimization for speed reasons")

    appconfig.reset_defaults()

    appconfig.actions.image[0].jobcontrol.countdown_capture = 0.2
    appconfig.actions.collage[0].jobcontrol.countdown_capture = 0.2
    appconfig.actions.collage[0].jobcontrol.countdown_capture_second_following = 0.2
    appconfig.actions.animation[0].jobcontrol.countdown_capture = 0.2
    appconfig.actions.animation[0].jobcontrol.countdown_capture_second_following = 0.2
    appconfig.actions.video[0].jobcontrol.countdown_capture = 0.2

    yield


# @pytest.fixture(scope="module", autouse=True)
# def session_setup1():
#     print("test")
#     logger.warning("hallo")

#     yield "some stuff"
