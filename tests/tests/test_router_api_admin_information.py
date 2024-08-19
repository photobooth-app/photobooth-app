import logging
from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container
from photobooth.services.informationservice import InformationService

logger = logging.getLogger(name=None)


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


def test_get_stats_reset(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/information/sttscntr/reset")
    assert response.status_code == 204

def test_get_limits_reset(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/information/sttscntr/reset/limits")
    assert response.status_code == 204

def test_get_stats_reset_error(client_authenticated: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(InformationService, "stats_counter_reset", error_mock):
        response = client_authenticated.get("/admin/information/sttscntr/reset")
        assert response.status_code == 500

def test_get_limits_reset_error(client_authenticated: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(InformationService, "stats_counter_reset_field", error_mock):
        response = client_authenticated.get("/admin/information/sttscntr/reset/limits")
        assert response.status_code == 500
