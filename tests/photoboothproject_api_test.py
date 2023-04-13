import os
import sys
import tempfile
from PIL import Image

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.configsettings import settings
from fastapi.testclient import TestClient
from start import app, imageServers

client = TestClient(app)


def test_capturemode():
    response = client.get("/cmd/frameserver/capturemode")
    assert response.status_code == 204


def test_previewmode():
    response = client.get("/cmd/frameserver/previewmode")
    assert response.status_code == 204


def capture():
    tmpfilepath = tempfile.mktemp(suffix=".jpg", prefix="pytest_booth_")
    settings.misc.photoboothproject_image_directory = os.path.dirname(
        os.path.realpath(tmpfilepath)
    )
    response = client.post(
        "/cmd/capture",
        content=tmpfilepath,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    assert response.text == "Done"
    try:
        with Image.open(tmpfilepath) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes {exc}") from exc


def test_1pic_capture():
    imageServers.start()
    capture()
    imageServers.stop()


def test_collage():
    imageServers.start()
    for i in range(1, 4):
        capture()
    imageServers.stop()
