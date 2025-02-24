import time
from collections.abc import Generator
from unittest import mock
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from photobooth.appconfig import appconfig
from photobooth.application import app
from photobooth.container import container
from photobooth.services.collection import MediacollectionService


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        container.processing_service.trigger_action("image", 0)
        container.processing_service.wait_until_job_finished()

        container.share_service.limit_counter_reset_all()

        yield client
        container.stop()


def test_printing_disabled(client: TestClient):
    # default printing is disabled, try to print gives a 405

    response = client.post("/share/actions/latest/0")

    assert response.status_code == 200


@patch("subprocess.run")
def test_print_latest(mock_run: mock.Mock, client: TestClient):
    # enable printing
    appconfig.share.sharing_enabled = True

    response = client.post("/share/actions/latest/0")

    assert response.status_code == 200
    mock_run.assert_called()


@patch("subprocess.run")
def test_print_specific_id(mock_run: mock.Mock, client: TestClient):
    appconfig.share.sharing_enabled = True

    # get an image to print
    mediaitem = container.mediacollection_service.get_item_latest()

    response = client.post(f"/share/actions/{mediaitem.id}/0")

    assert response.status_code == 200
    mock_run.assert_called()


@patch("subprocess.run")
def test_print_exception(mock_run: mock.Mock, client: TestClient):
    # ensure 500 is sent if exception during enabled printing service (process command fails for example)
    mock_run.side_effect = Exception("mock error")

    appconfig.share.sharing_enabled = True

    response = client.post("/share/actions/latest/0")

    assert response.status_code == 500
    mock_run.assert_called()


@patch("subprocess.run")
def test_print_check_blocking(mock_run: mock.Mock, client: TestClient):
    # get config
    appconfig.share.sharing_enabled = True
    appconfig.share.actions[0].processing.share_blocked_time = 2

    response = client.post("/share/actions/latest/0")

    time.sleep(appconfig.share.actions[0].processing.share_blocked_time / 2)

    response = client.post("/share/actions/latest/0")  # should be blocked and error

    assert response.status_code == 200  # gives 200 nowadays, triggers separate event.
    mock_run.assert_called()

    # wait a little more until printing is fine again
    time.sleep((appconfig.share.actions[0].processing.share_blocked_time / 2) + 0.2)

    response = client.post("/share/actions/latest/0")  # should give no error again

    assert response.status_code == 200
    mock_run.assert_called()


def test_latest_filenotfound_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = FileNotFoundError()

    with patch.object(MediacollectionService, "get_item_latest", error_mock):
        response = client.post("/share/actions/latest/0")
        assert response.status_code == 404
        assert "detail" in response.json()


def test_id_filenotfound_exception(client: TestClient):
    response = client.post(f"/share/actions/{uuid4()}/0")
    assert response.status_code == 404
    assert "detail" in response.json()
