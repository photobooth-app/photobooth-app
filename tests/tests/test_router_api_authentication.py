import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        yield client
        container.stop()


@pytest.fixture(scope="module")
def test_user():
    return {"username": "admin", "password": "0000"}


def test_login(client: TestClient, test_user):
    response = client.post("/admin/auth/token", data=test_user)
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert token is not None
    return token
