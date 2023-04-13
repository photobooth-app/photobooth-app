import os
import sys

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from start import app

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200

    # ensure no cache on main page so frontent updates work fine
    assert (
        "cache-control" in response.headers
        and "no-store, no-cache, must-revalidate" == response.headers["cache-control"]
    )


def test_read_config_scheme():
    response = client.get("/config/schema?schema_type=dereferenced")
    assert response.status_code == 200
