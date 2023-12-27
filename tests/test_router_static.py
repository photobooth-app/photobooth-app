import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.services.config import AppConfig, appconfig

appconfig.__dict__.update(AppConfig())


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        yield client
        client.app.container.shutdown_resources()


def test_read_main(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200

    # ensure no cache on main page so frontent updates work fine
    assert "cache-control" in response.headers and "no-store, no-cache, must-revalidate" == response.headers["cache-control"]


def test_read_log(client: TestClient):
    response = client.get("/debug/log/latest")
    assert response.status_code == 200


"""
def test_read_services_status(client: TestClient):
    response = client.get("/debug/service/status")
    assert response.status_code == 200

    # add shutdown_resources here, since appcontainer is fully initialized when getting this URI
    # failing to do so leaves threads running infinite.
    client.app.container.shutdown_resources()   # this mutes logging during pytest. remove test for now, check later.
"""
