from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from photobooth.appconfig import AppConfig
from photobooth.application import app
from photobooth.container import container


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        yield client
        container.stop()


def test_config_endpoints_ui(client: TestClient):
    response = client.get("/config")
    assert response.status_code == 200

    AppConfig.model_validate(response.json())
