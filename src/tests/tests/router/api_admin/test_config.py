import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from photobooth.appconfig import AppConfig


def test_config_endpoints_ui(client_authenticated: TestClient):
    response = client_authenticated.get("/config")
    assert response.status_code == 200

    AppConfig.model_validate(response.json())


def test_config_getschema(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/config/app/schema")
    assert response.status_code == 200
    response = client_authenticated.get("/admin/config/app/schema?schema_type=dereferenced")
    assert response.status_code == 200


def test_list_configurable(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/config/list")
    assert response.status_code == 200


def test_config_post_validationerror(client_authenticated: TestClient):
    config_dict = json.loads(AppConfig().model_dump_json())
    # set illegal setting, that provokes validation error
    config_dict["common"]["logging_level"] = "illegalsetting"

    response = client_authenticated.patch("/admin/config/app", json=config_dict)

    assert response.status_code == 422

    # config is changed by this command - revert it do avoid affecting other tests.
    AppConfig().deleteconfig()


def test_config_patch(client_authenticated: TestClient):
    # jsonify using pydantic's json function, because fastapi cannot convert all types (like Color)
    config_dict = json.loads(AppConfig().model_dump_json(context={"secrets_is_allowed": True}))

    response = client_authenticated.patch("/admin/config/app", json=config_dict)
    assert response.status_code == 200

    # config is changed by this command - revert it do avoid affecting other tests.
    AppConfig().deleteconfig()


@patch("os.remove")
def test_config_reset(mock_remove, client_authenticated: TestClient):
    response = client_authenticated.delete("/admin/config/app")

    assert response.status_code == 200

    # check os.remove was invoked
    mock_remove.assert_called()
