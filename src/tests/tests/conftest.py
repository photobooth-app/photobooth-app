import logging
from collections.abc import Generator
from multiprocessing import set_start_method

import pytest
from fastapi.testclient import TestClient
from gpiozero import Device
from gpiozero.pins.mock import MockFactory

from photobooth.appconfig import appconfig
from photobooth.application import app
from photobooth.container import container
from photobooth.database.database import create_db_and_tables

logger = logging.getLogger(name=None)

# globally set device pin_factory to mock
Device.pin_factory = MockFactory()


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/api/") as client:
        if not container.is_started():
            container.start()

        yield client

        container.stop()


@pytest.fixture
def client_authenticated(client: TestClient) -> Generator[TestClient, None, None]:
    response = client.post("/admin/auth/token", data={"username": "admin", "password": "0000"})
    token = response.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client


@pytest.fixture(scope="function", autouse=True)
def global_function_setup1():
    logger.info("global function-scoped mediaitem setup")

    if container.mediacollection_service.count() == 0:
        logger.info("no mediaitem in collection, creating one image")
        if not container.is_started():
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
    appconfig.actions.video[0].processing.video_duration = 2

    yield


@pytest.fixture(scope="session", autouse=True)
def session_setup1():
    create_db_and_tables()

    yield


@pytest.fixture(scope="session", autouse=True)
def session_setup2():
    # unify multiprocessing start method to spawn (otherwise fork for linux, spawn for win/mac)
    set_start_method("spawn")

    yield
