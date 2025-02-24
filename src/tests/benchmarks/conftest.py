import logging

import pytest

from photobooth.appconfig import appconfig
from photobooth.database.database import create_db_and_tables

logger = logging.getLogger(name=None)


@pytest.fixture(scope="function", autouse=True)
def global_function_setup2():
    logger.info("global function-scoped appconfig reset and optimization for speed reasons")

    appconfig.reset_defaults()

    appconfig.actions.image[0].jobcontrol.countdown_capture = 0.0
    appconfig.actions.collage[0].jobcontrol.countdown_capture = 0.0
    appconfig.actions.collage[0].jobcontrol.countdown_capture_second_following = 0.0
    appconfig.actions.collage[0].jobcontrol.approve_autoconfirm_timeout = 0.0
    appconfig.actions.animation[0].jobcontrol.countdown_capture = 0.0
    appconfig.actions.animation[0].jobcontrol.countdown_capture_second_following = 0.0
    appconfig.actions.animation[0].jobcontrol.approve_autoconfirm_timeout = 0.0
    appconfig.actions.video[0].jobcontrol.countdown_capture = 0.0
    appconfig.actions.multicamera[0].jobcontrol.countdown_capture = 0.0

    yield


@pytest.fixture(scope="session", autouse=True)
def session_setup1():
    create_db_and_tables()

    yield
