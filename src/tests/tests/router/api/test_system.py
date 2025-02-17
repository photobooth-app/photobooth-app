import platform
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/api/system") as client:
        container.start()
        yield client
        container.stop()


@pytest.fixture(params=["/host/reboot", "/host/shutdown"])
def system_host_endpoint(request):
    yield request.param


@pytest.fixture(params=["/service/reload"])
def system_service_endpoint(request):
    yield request.param


@pytest.fixture(params=["/systemctl/start", "/systemctl/restart", "/systemctl/stop"])
def system_systemctl_endpoint(request):
    yield request.param


@pytest.fixture(params=["/systemctl/install", "/systemctl/uninstall"])
def system_systemctl_installuninstall_endpoint(request):
    yield request.param


@pytest.fixture(params=["/host/xxx", "/service/xxx", "/systemctl/xxx"])
def system_nonexistant_endpoint(request):
    yield request.param


@patch("os.system")
def test_system_host_endpoints(mock_system: MagicMock, client: TestClient, system_host_endpoint):
    response = client.get(system_host_endpoint)
    assert response.status_code == 200

    mock_system.assert_called()


def test_system_service_endpoints(client: TestClient, system_service_endpoint):
    with patch.object(container, "reload") as mock_reload:
        response = client.get(system_service_endpoint)
        assert response.status_code == 200

        mock_reload.assert_called()


def test_system_systemctl_endpoints(client: TestClient, system_systemctl_endpoint):
    with patch.object(container.system_service, "util_systemd_control") as mock:
        response = client.get(system_systemctl_endpoint)
        assert response.status_code == 200

        mock.assert_called()


@patch("subprocess.run")
def test_system_systemctl_installuninstall_endpoints(mock_run: MagicMock, client: TestClient, system_systemctl_installuninstall_endpoint):
    response = client.get(system_systemctl_installuninstall_endpoint)

    if platform.system() == "Linux":
        assert response.status_code == 200
        mock_run.assert_called()
    else:
        assert response.status_code == 500


def test_system_nonexistant_endpoint(client: TestClient, system_nonexistant_endpoint):
    response = client.get(system_nonexistant_endpoint)
    assert response.status_code == 422
