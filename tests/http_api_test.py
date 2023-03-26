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
    # assert response.json() == {"msg": "Hello World"}


def test_read_config_scheme():
    response = client.get("/config/schema?schema_type=dereferenced")
    assert response.status_code == 200
