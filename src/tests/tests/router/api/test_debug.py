from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_read_log(client: TestClient):
    response = client.get("/debug/log/latest")
    assert response.status_code == 200


def test_read_log_err(client: TestClient):
    with patch.object(Path, "read_text", side_effect=RuntimeError()):
        response = client.get("/debug/log/latest")

        assert response.status_code == 500
        assert "detail" in response.json()
