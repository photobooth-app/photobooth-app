from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.routers.auth_dependencies_bearer import User


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/api/") as client:
        yield client


@pytest.fixture
def client_authenticated(client: TestClient) -> Generator[TestClient, None, None]:
    response = client.post("/admin/auth/token", data={"username": "admin", "password": "0000"})
    token = response.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client


@pytest.fixture(scope="module")
def test_user():
    return {"username": "admin", "password": "0000"}


@pytest.fixture(scope="module")
def test_user_nonexistant_username():
    return {"username": "admin_nonexists", "password": "doesntmatter"}


@pytest.fixture(scope="module")
def test_user_wrong_pw():
    return {"username": "admin", "password": "wrongPW"}


def test_login(client: TestClient, test_user):
    response = client.post("/admin/auth/token", data=test_user)
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert token is not None


def test_login_wrong_user(client: TestClient, test_user_nonexistant_username):
    response = client.post("/admin/auth/token", data=test_user_nonexistant_username)
    assert response.status_code == 401
    json = response.json()
    assert json.get("access_token", None) is None
    assert json.get("detail", None) is not None


def test_login_user_ok_password_wrong(client: TestClient, test_user_wrong_pw):
    response = client.post("/admin/auth/token", data=test_user_wrong_pw)
    assert response.status_code == 401
    json = response.json()
    assert json.get("access_token", None) is None
    assert json.get("detail", None) is not None


def test_user_me(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/auth/me")
    assert response.status_code == 200
    user = response.json()

    User.model_validate(user)
