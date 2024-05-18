import time
from unittest import mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from photobooth.application import app
from photobooth.container import container
from photobooth.services.config import appconfig


@pytest.fixture
def client() -> TestClient:
    with TestClient(app=app, base_url="http://test/api/") as client:
        container.start()
        container.processing_service.trigger_action("image", 0)
        container.processing_service.wait_until_job_finished()
        yield client
        container.stop()


def test_printing_disabled(client: TestClient):
    # default printing is disabled, try to print gives a 405

    response = client.get("/printer/print/latest/0")

    assert response.status_code == 200


@patch("subprocess.run")
def test_print_latest(mock_run: mock.Mock, client: TestClient):
    # enable printing
    appconfig.hardwareinputoutput.printing_enabled = True

    response = client.get("/printer/print/latest/0")

    assert response.status_code == 200
    mock_run.assert_called()


@patch("subprocess.run")
def test_print_specific_id(mock_run: mock.Mock, client: TestClient):
    appconfig.hardwareinputoutput.printing_enabled = True

    # get an image to print
    mediaitem = container.mediacollection_service.db_get_most_recent_mediaitem()

    response = client.get(f"/printer/print/{mediaitem.id}/0")

    assert response.status_code == 200
    mock_run.assert_called()


@patch("subprocess.run")
def test_print_exception(mock_run: mock.Mock, client: TestClient):
    # ensure 500 is sent if exception during enabled printing service (process command fails for example)
    mock_run.side_effect = Exception("mock error")

    appconfig.hardwareinputoutput.printing_enabled = True

    response = client.get("/printer/print/latest/0")

    assert response.status_code == 500
    mock_run.assert_called()


@patch("subprocess.run")
def test_print_check_blocking(mock_run: mock.Mock, client: TestClient):
    # get config
    appconfig.hardwareinputoutput.printing_enabled = True
    appconfig.printer.print[0].processing.printing_blocked_time = 2

    response = client.get("/printer/print/latest/0")

    time.sleep(appconfig.printer.print[0].processing.printing_blocked_time / 2)

    response = client.get("/printer/print/latest/0")  # should be blocked and error

    assert response.status_code == 200  # gives 200 nowadays, triggers separate event.
    mock_run.assert_called()

    # wait a little more until printing is fine again
    time.sleep((appconfig.printer.print[0].processing.printing_blocked_time / 2) + 0.2)

    response = client.get("/printer/print/latest/0")  # should give no error again

    assert response.status_code == 200
    mock_run.assert_called()
