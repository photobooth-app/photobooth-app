import os
import sys

from fastapi.testclient import TestClient

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_read_main():
    from start import app

    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200

    # ensure no cache on main page so frontent updates work fine
    assert (
        "cache-control" in response.headers
        and "no-store, no-cache, must-revalidate" == response.headers["cache-control"]
    )


def test_read_log():
    from start import app

    client = TestClient(app)

    response = client.get("/log/latest")
    assert response.status_code == 200
