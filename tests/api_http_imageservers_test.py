import io
import os
import sys

from fastapi.testclient import TestClient
from PIL import Image

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_api_imageservers_modes():
    import time

    from start import app

    client = TestClient(app)

    response = client.get("/api/imageservers/capturemode")
    assert response.status_code == 202

    time.sleep(2.0)

    response = client.get("/api/imageservers/previewmode")
    assert response.status_code == 202


def test_api_imageservers_still():
    from start import app, imageServers

    client = TestClient(app)
    imageServers.start()

    response = client.get("/api/imageservers/still")
    try:
        with Image.open(io.BytesIO(response.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(
            f"backend did not return valid image bytes, {exc}"
        ) from exc

    assert response.status_code == 200

    imageServers.stop()
