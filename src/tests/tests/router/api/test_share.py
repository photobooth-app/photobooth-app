import time
from collections.abc import Generator
from unittest import mock
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from photobooth.appconfig import appconfig
from photobooth.container import container
from photobooth.services.collection import MediacollectionService


@pytest.fixture(scope="module")
def modules_client(client) -> Generator[TestClient, None, None]:
    appconfig.share.sharing_enabled = True

    container.reload()
    yield client
    container.stop()


@pytest.fixture(autouse=True)
def fixture_reset():
    container.share_service.limit_counter_reset_all()


@patch("subprocess.run")
def test_print_latest(mock_run: mock.Mock, modules_client: TestClient):
    # enable printing

    container.processing_service.trigger_action("image", 0)
    container.processing_service.wait_until_job_finished()

    response = modules_client.post("/share/actions/latest/0")

    assert response.status_code == 200
    mock_run.assert_called()


@patch("subprocess.run")
def test_print_specific_id(mock_run: mock.Mock, modules_client: TestClient):
    # get an image to print
    container.processing_service.trigger_action("image", 0)
    container.processing_service.wait_until_job_finished()
    mediaitem = container.mediacollection_service.get_item_latest()

    response = modules_client.post(f"/share/actions/{mediaitem.id}/0")

    assert response.status_code == 200
    mock_run.assert_called()


@patch("subprocess.run")
def test_print_exception(mock_run: mock.Mock, modules_client: TestClient):
    # ensure 500 is sent if exception during enabled printing service (process command fails for example)
    mock_run.side_effect = Exception("mock error")

    container.processing_service.trigger_action("image", 0)
    container.processing_service.wait_until_job_finished()

    response = modules_client.post("/share/actions/latest/0")

    assert response.status_code == 500
    mock_run.assert_called()


@patch("subprocess.run")
def test_print_check_blocking(mock_run: mock.Mock, modules_client: TestClient):
    # get config
    appconfig.share.actions[0].processing.share_blocked_time = 2
    container.processing_service.trigger_action("image", 0)
    container.processing_service.wait_until_job_finished()

    response = modules_client.post("/share/actions/latest/0")

    time.sleep(appconfig.share.actions[0].processing.share_blocked_time / 2)

    response = modules_client.post("/share/actions/latest/0")  # should be blocked and error

    assert response.status_code == 200  # gives 200 nowadays, triggers separate event.
    mock_run.assert_called()

    # wait a little more until printing is fine again
    time.sleep((appconfig.share.actions[0].processing.share_blocked_time / 2) + 0.2)

    response = modules_client.post("/share/actions/latest/0")  # should give no error again

    assert response.status_code == 200
    mock_run.assert_called()


def test_latest_filenotfound_exception(modules_client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = FileNotFoundError()

    with patch.object(MediacollectionService, "get_item_latest", error_mock):
        response = modules_client.post("/share/actions/latest/0")
        assert response.status_code == 404
        assert "detail" in response.json()


def test_id_filenotfound_exception(modules_client: TestClient):
    response = modules_client.post(f"/share/actions/{uuid4()}/0")
    assert response.status_code == 404
    assert "detail" in response.json()
