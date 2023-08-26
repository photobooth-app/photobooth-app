import platform
from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.services.systemservice import SystemService


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        yield client
        client.app.container.shutdown_resources()


@pytest.fixture(
    params=[
        "/system/service/start",
        "/system/service/restart",
        "/system/service/stop",
    ]
)
def system_service_startstop_endpoint(request):
    yield request.param


@pytest.fixture(
    params=[
        "/system/service/reload",
    ]
)
def system_service_reload_endpoint(request):
    yield request.param


@pytest.fixture(
    params=[
        "/system/server/reboot",
        "/system/server/shutdown",
    ]
)
def system_server_endpoint(request):
    yield request.param


@pytest.fixture(
    params=[
        "/system/service/install",
        "/system/service/uninstall",
    ]
)
def system_service_installuninstall_endpoint(request):
    yield request.param


def test_system_service_startstop_endpoints(client: TestClient, system_service_startstop_endpoint):
    system_service_mock = mock.Mock(spec=SystemService)

    with patch.object(system_service_mock, "util_systemd_control"):
        with app.container.services.system_service.override(system_service_mock):
            response = client.get(system_service_startstop_endpoint)
            assert response.status_code == 200

            system_service_mock.util_systemd_control.assert_called()


def test_system_service_reload_endpoints(client: TestClient, system_service_reload_endpoint):
    with patch.object(client.app.container, "shutdown_resources"):
        with patch.object(client.app.container, "init_resources"):
            response = client.get(system_service_reload_endpoint)
            assert response.status_code == 200

            client.app.container.shutdown_resources.assert_called()
            client.app.container.init_resources.assert_called()


@patch("os.system")
def test_system_server_endpoints(mock_system, client: TestClient, system_server_endpoint):
    response = client.get(system_server_endpoint)
    assert response.status_code == 200

    mock_system.assert_called()


@patch("subprocess.run")
def test_system_service_installuninstall_endpoints(
    mock_run, client: TestClient, system_service_installuninstall_endpoint
):
    response = client.get(system_service_installuninstall_endpoint)

    if platform.system() == "Linux":
        assert response.status_code == 200
        mock_run.assert_called()
    else:
        assert response.status_code == 500


def test_system_nonexistant_endpoint(client: TestClient):
    response = client.get("/system/actionis/forsurenonexistent")
    assert response.status_code == 500
