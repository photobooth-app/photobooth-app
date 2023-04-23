import os
import sys
import pytest

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from src.configsettings import ConfigSettings


@pytest.fixture(
    params=[
        "/config/ui",
        "/config/schema?schema_type=dereferenced",
        "/config/currentActive",
        "/config/current",
    ]
)
def config_endpoint(request):
    # setup
    yield request.param
    # cleanup


def test_config_endpoints(config_endpoint):
    from start import app

    client = TestClient(app)

    response = client.get(config_endpoint)
    assert response.status_code == 200


def test_config_post():
    from start import app

    client = TestClient(app)

    response = client.post(
        "/config/current", json={"updated_settings": ConfigSettings().dict()}
    )
    assert response.status_code == 200
