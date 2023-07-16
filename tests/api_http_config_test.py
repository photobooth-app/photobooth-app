import json

import pytest
from fastapi.testclient import TestClient

from photobooth.appconfig import AppConfig
from photobooth.application import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture(
    params=[
        "/config/ui",
        "/config/schema?schema_type=dereferenced",
        "/config/currentActive",
        "/config/current",
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
    config_dict = {"updated_settings": json.loads(AppConfig().model_dump_json())}

    response = client.post("/config/current", json=config_dict)
    assert response.status_code == 200
