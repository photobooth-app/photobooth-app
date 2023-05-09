import os
import sys

from fastapi.testclient import TestClient

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_chose_1pic():
    from start import app, imageServers, processingpicture

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
