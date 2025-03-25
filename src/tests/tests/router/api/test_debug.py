from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/") as client:
        container.start()
        yield client
        container.stop()


def test_read_log(client: TestClient):
    response = client.get("/api/debug/log/latest")
    assert response.status_code == 200


def test_read_log_err(client: TestClient):
    with patch.object(Path, "read_text", side_effect=RuntimeError()):
        response = client.get("/api/debug/log/latest")

        assert response.status_code == 500
        assert "detail" in response.json()
