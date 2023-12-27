"""
Testing virtual camera Backend
"""
import json
import logging
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.services.config import AppConfig, appconfig


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


logger = logging.getLogger(name=None)


def test_app_runtime_exc_folder_creation_failed():
    import photobooth.application

    with patch.object(os, "makedirs", side_effect=RuntimeError("effect: failed creating folder")):
        # emulate write access issue and ensure an exception is received to make the app fail starting.
        with pytest.raises(RuntimeError):
            photobooth.application._create_app()


@pytest.fixture
def client() -> TestClient:
    from photobooth.application import app

    with TestClient(app=app, base_url="http://test") as client:
        yield client
        client.app.container.shutdown_resources()


def test_config_post_validationerror(client: TestClient):
    config_dict = json.loads(AppConfig().model_dump_json())
    # set illegal setting, that provokes validation error
    config_dict["common"]["countdown_capture_first"] = -1

    response = client.post("/admin/config/current", json=config_dict)

    assert response.status_code == 422
