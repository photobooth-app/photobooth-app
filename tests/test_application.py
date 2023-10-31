"""
Testing Simulated Backend
"""
import json
import logging
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.appconfig import AppConfig

logger = logging.getLogger(name=None)


def test_app_runtime_exc_folder_creation_failed():
    with patch.object(os, "makedirs", side_effect=OSError("test")):
        # emulate write access issue and ensure an exception is received to make the app fail starting.
        with pytest.raises(OSError):
            from photobooth.application import app

            _ = app


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
