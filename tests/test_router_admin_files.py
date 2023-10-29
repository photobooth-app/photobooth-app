import os
from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.routers.admin.files import PathListItem


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        yield client
        client.app.container.shutdown_resources()


@pytest.fixture(
    params=[
        "/admin/files/list/",
        "/admin/files/list/userdata",
    ]
)
def admin_files_endpoint(request):
    # setup
    yield request.param
    # cleanup


def test_admin_simple_endpoints(client: TestClient, admin_files_endpoint):
    response = client.get(admin_files_endpoint)
    assert response.status_code == 200


def test_admin_file_endpoints(client: TestClient):
    open(".testfile", "a").close()

    response = client.get("/admin/files/file/.testfile")

    os.remove(".testfile")

    assert response.status_code == 200


def test_admin_file_notexists_endpoints(client: TestClient):
    # open(".testfile", "a").close()

    response = client.get("/admin/files/file/.testfile_notexistant")

    assert response.status_code == 404


def test_admin_files_zip_post(client: TestClient):
    # make up a list - only filepath needs to be valid for this function.
    selected_files = [asdict(PathListItem(name="log", filepath="./log", is_dir=True, size=0))]

    response = client.post("/admin/files/zip", json=selected_files)
    assert response.status_code == 200
