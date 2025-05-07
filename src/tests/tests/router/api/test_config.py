from fastapi.testclient import TestClient

from photobooth.appconfig import AppConfig


def test_config_endpoints_ui(client: TestClient):
    response = client.get("/config")
    assert response.status_code == 200

    AppConfig.model_validate(response.json())
