import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import photobooth.routers.userdata as userdata_router
from photobooth.routers.userdata import api_get_userfiles


def test_get_404_missing_item(client: TestClient):
    response = client.get("../userdata/nonexistant/file.png")
    assert response.status_code == 404


def test_get(client: TestClient):
    tmpfile = NamedTemporaryFile(mode="wb", delete=False, dir="userdata/", prefix="tmptestuserdata_", suffix=".dummy")
    tmpfile.close()  # close so its accessible for reading by http

    response = client.get(f"../userdata/{Path(tmpfile.name).name}")
    assert response.status_code == 200

    os.unlink(tmpfile.name)


def test_get_file_from_demofolder(client: TestClient):
    assert Path("userdata/demoassets/frames/frame_image_photobooth-app.png").is_file()
    response = client.get("../userdata/demoassets/frames/frame_image_photobooth-app.png")
    assert response.status_code == 200


def test_demoassets_are_served_from_package_when_userdata_is_elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(userdata_router, "USERDATA_PATH", str(tmp_path / "userdata"))

    response = api_get_userfiles("demoassets/frames/frame_image_photobooth-app.png")

    expected_path = Path(userdata_router.__file__).resolve().parents[1] / "demoassets" / "userdata" / "frames" / "frame_image_photobooth-app.png"
    assert Path(response.path) == expected_path


def test_get_400_on_illegal():
    with pytest.raises(HTTPException) as exc_info:
        api_get_userfiles("../../../test/illegal-file")

    assert exc_info.value.status_code == 400


def test_get_rejects_demoassets_traversal():
    with pytest.raises(HTTPException) as exc_info:
        api_get_userfiles("demoassets/../../../../etc/passwd")

    assert exc_info.value.status_code == 400
