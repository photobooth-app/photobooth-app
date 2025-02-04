import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container
from photobooth.services.config import AppConfig


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        yield client
        container.stop()


@pytest.fixture
def client_authenticated(client) -> TestClient:
    response = client.post("/admin/auth/token", data={"username": "admin", "password": "0000"})
    token = response.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client


@pytest.fixture(
    params=[
        "/config/current",  # without password protection, UI reads the config
        "/admin/config/schema?schema_type=dereferenced",
        "/admin/config/current",
        "/admin/config/default",
    ]
)
def config_endpoint(request):
    # setup
    yield request.param
    # cleanup


def test_config_endpoints(client_authenticated: TestClient, config_endpoint):
    response = client_authenticated.get(config_endpoint)
    assert response.status_code == 200


def test_config_post_validationerror(client_authenticated: TestClient):
    config_dict = json.loads(AppConfig().model_dump_json())
    # set illegal setting, that provokes validation error
    config_dict["common"]["logging_level"] = "illegalsetting"

    response = client_authenticated.post("/admin/config/current", json=config_dict)

    assert response.status_code == 422

    # config is changed by this command - revert it do avoid affecting other tests.
    AppConfig().deleteconfig()


def test_config_post(client_authenticated: TestClient):
    # jsonify using pydantic's json function, because fastapi cannot convert all types (like Color)
    config_dict = json.loads(AppConfig().model_dump_json())

    response = client_authenticated.post("/admin/config/current", json=config_dict)
    assert response.status_code == 200

    # config is changed by this command - revert it do avoid affecting other tests.
    AppConfig().deleteconfig()


@patch("os.remove")
def test_config_reset(mock_remove, client_authenticated: TestClient):
    response = client_authenticated.get("/admin/config/reset")

    assert response.status_code == 200

    # check os.remove was invoked
    mock_remove.assert_called()
