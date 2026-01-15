import os
from pathlib import Path

from fastapi.testclient import TestClient

from photobooth import USERDATA_PATH


def test_read_web_spa(client: TestClient):
    response = client.get("../")
    assert response.status_code == 200

    # ensure no cache on main page so frontent updates work fine
    assert "cache-control" in response.headers and "no-cache" == response.headers["cache-control"]


def test_read_web_sharepage(client: TestClient):
    response = client.get("../sharepage/")
    assert response.status_code == 200


def test_private_css_nonexisting_placeholder(client: TestClient):
    private_css_file = Path(USERDATA_PATH, "private.css")
    try:
        os.remove(private_css_file)
    except Exception:
        # ignore if file not exists
        pass

    assert not private_css_file.exists()

    response = client.get("../private.css")
    assert response.status_code == 200
    assert response.text.strip().startswith("/*")
    assert response.text.strip().endswith("*/")


def test_private_css(client: TestClient):
    TEST_STRING = "/*css-test-content*/"
    os.makedirs(USERDATA_PATH, exist_ok=True)
    with open(Path(USERDATA_PATH, "private.css"), "w") as private_css_file:
        private_css_file.write(TEST_STRING)
        private_css_file.flush()

    response = client.get("../private.css")
    assert Path(USERDATA_PATH, "private.css").exists()
    assert response.status_code == 200
    assert response.text.strip() == TEST_STRING
