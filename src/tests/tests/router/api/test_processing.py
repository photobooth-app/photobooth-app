import io
import logging
from pathlib import Path
from unittest import mock
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from photobooth.container import container
from photobooth.services.processing import ProcessingService
from photobooth.services.processor.base import Capture

from ...util import get_jpeg

logger = logging.getLogger(name=None)


def test_chose_video_stoprecording(client: TestClient):
    with patch.object(container.processing_service, "queue_external_event") as mock:
        # emulate action
        response = client.get("/processing/next")
        assert response.status_code == 200

        mock.assert_called_with("next")


def test_confirm_reject_abort(client: TestClient):
    with patch.object(container.processing_service, "continue_process") as mock:
        # emulate action
        response = client.get("/processing/confirm")
        assert response.status_code == 200

        mock.assert_called()

    with patch.object(container.processing_service, "reject_capture") as mock:
        # emulate action
        response = client.get("/processing/reject")
        assert response.status_code == 200

        mock.assert_called()

    with patch.object(container.processing_service, "abort_process") as mock:
        # emulate action
        response = client.get("/processing/abort")
        assert response.status_code == 200

        mock.assert_called()


def test_confirm_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(ProcessingService, "continue_process", error_mock):
        response = client.get("/processing/confirm")
        assert response.status_code == 500
        assert "detail" in response.json()


def test_reject_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(ProcessingService, "reject_capture", error_mock):
        response = client.get("/processing/reject")
        assert response.status_code == 500
        assert "detail" in response.json()


def test_abort_exception(client: TestClient):
    error_mock = mock.MagicMock()
    error_mock.side_effect = Exception()

    with patch.object(ProcessingService, "abort_process", error_mock):
        response = client.get("/processing/abort")
        assert response.status_code == 500
        assert "detail" in response.json()


def test_api_get_preview_image_filtered_success(client: TestClient, tmp_path: Path):
    capture_id = uuid4()
    file_in = Path(tmp_path, "file_in.jpg")
    file_in.write_bytes(get_jpeg((800, 500)).getbuffer())

    fake_capture = Capture(filepath=file_in, uuid=capture_id)

    with patch("photobooth.services.processing.ProcessingService.get_capture", return_value=fake_capture):
        response = client.get(f"/processing/approval/{capture_id}")
        assert response.status_code == 200

        # Response should be a valid image
        img = Image.open(io.BytesIO(response.content))
        img.verify()


def test_api_get_preview_image_filtered_not_found(client: TestClient):
    capture_id = uuid4()

    with patch("photobooth.services.processing.ProcessingService.get_capture", side_effect=FileNotFoundError("not found")):
        response = client.get(f"/processing/approval/{capture_id}")
        assert response.status_code == 404
        assert "cannot be found" in response.json()["detail"]
