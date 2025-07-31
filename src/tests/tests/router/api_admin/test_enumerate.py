import logging

from fastapi.testclient import TestClient

logger = logging.getLogger(name=None)


def test_admin_enumerate_serialports(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/enumerate/serialports")
    assert response.status_code == 200
    assert len(response.json()) > 1


def test_admin_enumerate_usbcameras(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/enumerate/usbcameras")
    assert response.status_code == 200
    assert len(response.json()) > 1


def test_admin_enumerate_files(client_authenticated: TestClient):
    response = client_authenticated.get("/admin/enumerate/userfiles?q=.")
    assert response.status_code == 200
    assert len(response.json()) > 1
