import os
from collections.abc import Generator
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container
from photobooth.routers.userdata import api_get_userfiles


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/") as client:
        container.start()
        yield client
        container.stop()


def test_get_404_missing_item(client: TestClient):
    response = client.get("/userdata/nonexistant/file.png")
    assert response.status_code == 404


def test_get(client: TestClient):
    tmpfile = NamedTemporaryFile(mode="wb", delete=False, dir="userdata/", prefix="tmptestuserdata_", suffix=".dummy")
    tmpfile.close()  # close so its accessible for reading by http

    response = client.get(f"/userdata/{Path(tmpfile.name).name}")
    assert response.status_code == 200

    os.unlink(tmpfile.name)


def test_get_file_from_demofolder(client: TestClient):
    assert Path("userdata/demoassets/frames/frame_image_photobooth-app.png").is_file()
    response = client.get("/userdata/demoassets/frames/frame_image_photobooth-app.png")
    assert response.status_code == 200


def test_get_500_on_illegal():
    with pytest.raises(HTTPException) as exc_info:
        api_get_userfiles("/../../test/illegal-file")

    assert exc_info.value.status_code == 500
