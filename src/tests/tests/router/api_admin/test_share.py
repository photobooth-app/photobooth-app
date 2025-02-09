import logging
from collections.abc import Generator
from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container
from photobooth.services.share import ShareService

logger = logging.getLogger(name=None)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        yield client
        container.stop()


@pytest.fixture
def client_authenticated(client) -> Generator[TestClient, None, None]:
    response = client.post("/admin/auth/token", data={"username": "admin", "password": "0000"})
    token = response.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client


def test_get_stats_reset_all(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/share/cntr/reset/")
    assert response.status_code == 204


def test_get_stats_reset_all_error(client_authenticated: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(ShareService, "limit_counter_reset_all", error_mock):
        response = client_authenticated.get("/admin/share/cntr/reset/")
        assert response.status_code == 500


def test_get_limits_reset(client_authenticated: TestClient):
    container.share_service.limit_counter_increment("test_case")
    response = client_authenticated.get("/admin/share/cntr/reset/test_case")
    assert response.status_code == 204


def test_get_limits_reset_nonexistant_failsilent(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/share/cntr/reset/test_case_does_not_exist")
    assert response.status_code == 204


def test_get_limits_reset_error(client_authenticated: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(ShareService, "limit_counter_reset", error_mock):
        response = client_authenticated.get("/admin/share/cntr/reset/mockexctest")
        assert response.status_code == 500
