import sys
import os
import time
import io
import logging
from PIL import Image


# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.configsettings import settings
from fastapi.testclient import TestClient

logger = logging.getLogger(name=None)


def capture(client):
    response = client.get("/api/imageservers/still")
    try:
        with Image.open(io.BytesIO(response.content)) as img:
            img.verify()
    except Exception as exc:
        raise AssertionError(
            f"backend did not return valid image bytes, {exc}"
        ) from exc

    assert response.status_code == 200


def test_capturewithcapturemode():
    from start import app, imageServers, ins, processingpicture

    client = TestClient(app)
    processingpicture._reset()

    imageServers.start()
    ins.start()

    try:
        response = client.get("/api/imageservers/capturemode")
        assert response.status_code == 202

        # virtual countdown
        time.sleep(1)

        capture(client)

        response = client.get("/api/imageservers/previewmode")
        assert response.status_code == 202

    except Exception as exc:
        logger.exception(exc)
        raise RuntimeError("something is wrong")
    finally:
        imageServers.stop()
        ins.stop()


def test_capturewithoutcapturemode():
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


def test_collagewithcapturemode():
    from start import app, imageServers, ins, processingpicture

    client = TestClient(app)
    processingpicture._reset()
    imageServers.start()
    ins.start()

    try:
        for i in range(1, 4):
            response = client.get("/api/imageservers/capturemode")
            assert response.status_code == 202
            # bring statemachine to idle again

            # virtual countdown
            time.sleep(1)

            capture(client)

            response = client.get("/api/imageservers/previewmode")
            assert response.status_code == 202

    except Exception as exc:
        logger.exception(exc)
        raise RuntimeError("something is wrong")
    finally:
        imageServers.stop()
        ins.stop()


def test_collagewithoutcapturemode():
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
