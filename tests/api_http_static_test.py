import pytest
from fastapi.testclient import TestClient

from photobooth.application import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        yield client


def test_read_main(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200

    # ensure no cache on main page so frontent updates work fine
    assert (
        "cache-control" in response.headers
        and "no-store, no-cache, must-revalidate" == response.headers["cache-control"]
    )


def test_read_log(client: TestClient):
    response = client.get("/log/latest")
    assert response.status_code == 200
