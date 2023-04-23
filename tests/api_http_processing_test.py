import os
import sys
import pytest

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from src.configsettings import ConfigSettings


def test_reject_request_nonidle_statemachine():
    import time
    from start import app
    from start import imageServers
    from start import processingpicture

    client = TestClient(app)
    # reset statemachine
    processingpicture._reset()

    response = client.get("/cmd/imageserver/capturemode")
    assert response.status_code == 202

    time.sleep(0.25)

    # rejected since already thrilled
    response = client.get("/cmd/imageserver/capturemode")
    assert response.status_code == 400


def test_chose_1pic():
    from start import app
    from start import imageServers
    from start import processingpicture

    client = TestClient(app)
    processingpicture._reset()

    # no imageserver started yet, result 500
    response = client.get("/chose/1pic")
    assert response.status_code == 500

    # reset statemachine for next test
    processingpicture._reset()

    imageServers.start()

    response = client.get("/chose/1pic")
    assert response.status_code == 200

    # set statemachine to non-idle state and check next request is rejected
    processingpicture.thrill()

    response = client.get("/chose/1pic")
    assert response.status_code == 400

    imageServers.stop()
