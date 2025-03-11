import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from photobooth import USERDATA_PATH
from photobooth.application import app
from photobooth.container import container


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/") as client:
        container.start()
        yield client
        container.stop()


def test_read_main(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200

    # ensure no cache on main page so frontent updates work fine
    assert "cache-control" in response.headers and "no-store, no-cache, must-revalidate" == response.headers["cache-control"]


def test_private_css_nonexisting_placeholder(client: TestClient):
    private_css_file = Path(USERDATA_PATH, "private.css")
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
    os.makedirs(USERDATA_PATH, exist_ok=True)
    with open(Path(USERDATA_PATH, "private.css"), "w") as private_css_file:
        private_css_file.write(TEST_STRING)
        private_css_file.flush()

    response = client.get("/private.css")
    assert Path(USERDATA_PATH, "private.css").exists()
    assert response.status_code == 200
    assert response.text.strip() == TEST_STRING
