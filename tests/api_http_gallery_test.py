import pytest
from fastapi.testclient import TestClient

from photobooth.application import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test") as client:
        yield client
        client.app.container.shutdown_resources()


@pytest.fixture(
    params=[
        "/mediacollection/getitems",
    ]
)
def gallery_endpoint(request):
    # setup
    yield request.param
    # cleanup


def test_gallery_endpoints(client: TestClient, gallery_endpoint):
    response = client.get(gallery_endpoint)
    assert response.status_code == 200
