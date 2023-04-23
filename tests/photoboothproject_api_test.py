import sys
import os
import time
import tempfile
import logging
from PIL import Image


# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.configsettings import settings
from fastapi.testclient import TestClient

logger = logging.getLogger(name=None)


def capture(client):
    tmpfilepath = tempfile.mktemp(suffix=".jpg", prefix="pytest_booth_")
    settings.misc.photoboothproject_image_directory = os.path.dirname(
        os.path.realpath(tmpfilepath)
    )
    response = client.post(
        "/cmd/capture",
        content=tmpfilepath,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    # post returns and in this moment the file should be available...

    assert response.status_code == 200
    assert response.text == "Done"
    try:
        with Image.open(tmpfilepath) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(f"backend did not return valid image bytes {exc}") from exc


def test_capturewithcountdown():
    from start import app, imageServers, ins, processingpicture

    client = TestClient(app)
    processingpicture._reset()

    imageServers.start()
    ins.start()

    try:
        response = client.get("/cmd/imageserver/capturemode")
        assert response.status_code == 202
        # bring statemachine to idle again

        # virtual countdown
        time.sleep(1)

        capture(client)

        response = client.get("/cmd/imageserver/previewmode")
        assert response.status_code == 202

    except Exception as exc:
        logger.exception(exc)
        raise RuntimeError("something is wrong")
    finally:
        imageServers.stop()
        ins.stop()


def test_capturenocountdown():
    from start import app, imageServers, ins, processingpicture

    client = TestClient(app)
    processingpicture._reset()
    imageServers.start()
    ins.start()

    try:
        capture(client)
    finally:
        imageServers.stop()
        ins.stop()


def test_collagewithcountdown():
    from start import app, imageServers, ins, processingpicture

    client = TestClient(app)
    processingpicture._reset()
    imageServers.start()
    ins.start()

    try:
        for i in range(1, 4):
            response = client.get("/cmd/imageserver/capturemode")
            assert response.status_code == 202
            # bring statemachine to idle again

            # virtual countdown
            time.sleep(1)

            capture(client)

            response = client.get("/cmd/imageserver/previewmode")
            assert response.status_code == 202

    except Exception as exc:
        logger.exception(exc)
        raise RuntimeError("something is wrong")
    finally:
        imageServers.stop()
        ins.stop()


def test_collagenocountdown():
    from start import app, imageServers, ins, processingpicture

    client = TestClient(app)
    processingpicture._reset()
    imageServers.start()
    ins.start()

    try:
        for i in range(1, 4):
            capture(client)
            time.sleep(1)
    finally:
        imageServers.stop()
        ins.stop()
