import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container
from photobooth.services.config import appconfig


@pytest.fixture(autouse=True)
def run_around_tests():
    appconfig.reset_defaults()

    yield


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        container.start()
        yield client
        container.stop()


def test_read_main(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200

    # ensure no cache on main page so frontent updates work fine
    assert "cache-control" in response.headers and "no-store, no-cache, must-revalidate" == response.headers["cache-control"]


def test_read_log(client: TestClient):
    response = client.get("/debug/log/latest")
    assert response.status_code == 200


def test_private_css_nonexisting_placeholder(client: TestClient):
    private_css_file = Path("userdata", "private.css")
    try:
        os.remove(private_css_file)
    except Exception:
        # ignore if file not exists
        pass

    assert not private_css_file.exists()

    response = client.get("/private.css")
    assert response.status_code == 200
    assert response.text.strip().startswith("/*")
    assert response.text.strip().endswith("*/")


def test_private_css(client: TestClient):
    TEST_STRING = "/*css-test-content*/"
    os.makedirs("userdata", exist_ok=True)
    with open(Path("userdata", "private.css"), "w") as private_css_file:
        private_css_file.write(TEST_STRING)
        private_css_file.flush()

    response = client.get("/private.css")
    assert Path("userdata", "private.css").exists()
    assert response.status_code == 200
    assert response.text.strip() == TEST_STRING
