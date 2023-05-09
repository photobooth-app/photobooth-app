import os
import sys

import pytest
from fastapi.testclient import TestClient

# https://docs.python-guide.org/writing/structure/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(
    params=[
        "/gallery/images",
    ]
)
def gallery_endpoint(request):
    # setup
    yield request.param
    # cleanup


def test_gallery_endpoints(gallery_endpoint):
    from start import app

    client = TestClient(app)

    response = client.get(gallery_endpoint)
    assert response.status_code == 200
