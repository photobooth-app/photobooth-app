"""
Testing virtual camera Backend
"""
import json
import logging

import pytest
from fastapi.testclient import TestClient

from photobooth.container import container
from photobooth.services.config import AppConfig, appconfig

logger = logging.getLogger(name=None)


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


@pytest.fixture
def client() -> TestClient:
    from photobooth.application import app

    with TestClient(app=app, base_url="http://test") as client:
        container.start()
        yield client
        container.stop()


def test_app():
    import photobooth.application

    photobooth.application._create_app()


def test_config_post_validationerror(client: TestClient):
    config_dict = json.loads(AppConfig().model_dump_json())
    # set illegal setting, that provokes validation error
    config_dict["common"]["countdown_capture_first"] = -1

    response = client.post("/admin/config/current", json=config_dict)

    assert response.status_code == 422
