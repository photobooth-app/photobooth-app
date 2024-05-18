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


@pytest.fixture(
    params=[
        "/config/ui",
        "/admin/config/schema?schema_type=dereferenced",
        "/admin/config/currentActive",
        "/admin/config/current",
    ]
)
def config_endpoint(request):
    # setup
    yield request.param
    # cleanup


def test_config_endpoints(client: TestClient, config_endpoint):
    response = client.get(config_endpoint)
    assert response.status_code == 200


def test_config_post(client: TestClient):
    # jsonify using pydantic's json function, because fastapi cannot convert all types (like Color)
    config_dict = json.loads(AppConfig().model_dump_json())

    response = client.post("/admin/config/current", json=config_dict)
    assert response.status_code == 200


@patch("os.remove")
def test_config_reset(mock_remove, client: TestClient):
    response = client.get("/admin/config/reset")

    assert response.status_code == 200

    # check os.remove was invoked
    mock_remove.assert_called()
