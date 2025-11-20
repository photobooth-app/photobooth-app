from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from PIL import Image

# def test_calibration_stats_not_implemented(client_authenticated: TestClient):
#     response = client_authenticated.get("/admin/multicamera/calibration")
#     assert response.status_code == 500 or response.status_code == 501
#     # FastAPI will wrap NotImplementedError into 500 by default


# @patch("photobooth.utils.multistereo_calibration.charuco_board.generate_board")
def test_generate_charucoboard_success(client_authenticated: TestClient):
    req = {
        "squares_x": 14,
        "squares_y": 9,
        "square_length_mm": 20,
        "marker_length_mm": 15,
    }
    response = client_authenticated.post("/admin/multicamera/calibration/charuco", json=req)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


@patch("photobooth.routers.api_admin.multicamera.generate_board", side_effect=RuntimeError("fail"))
def test_generate_charucoboard_failure(mock, client_authenticated: TestClient):
    req = {
        "squares_x": 14,
        "squares_y": 9,
        "square_length_mm": 20,
        "marker_length_mm": 15,
    }

    response = client_authenticated.post("/admin/multicamera/calibration/charuco", json=req)
    assert response.status_code == 500
    assert "Failed to generate board" in response.json()["detail"]


@patch("photobooth.routers.api_admin.multicamera.SimpleCalibrationUtil")
def test_delete_calibration_success(mock_cu, client_authenticated: TestClient):
    response = client_authenticated.delete("/admin/multicamera/calibration")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_cu.return_value.delete_calibration_data.assert_called()


@patch("photobooth.routers.api_admin.multicamera.SimpleCalibrationUtil")
@patch("photobooth.routers.api_admin.multicamera.get_detector")
def test_post_calibrate_all_success(mock_get_detector, mock_cu, client_authenticated: TestClient, tmp_path: Path):
    # Fake calibration util methods
    mock_cu.return_value.calibrate_all.return_value = None
    mock_cu.return_value.save_calibration_data.return_value = None
    mock_get_detector.return_value = MagicMock()

    req = {
        "filess_in": [[str(tmp_path / "img0.jpg")]],
        "board_definition": {
            "squares_x": 14,
            "squares_y": 9,
            "square_length_mm": 20,
            "marker_length_mm": 15,
        },
    }
    response = client_authenticated.post("/admin/multicamera/calibration", json=req)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("photobooth.routers.api_admin.multicamera.SimpleCalibrationUtil")
@patch("photobooth.routers.api_admin.multicamera.get_detector")
def test_post_calibrate_all_failure(mock_get_detector, mock_cu, client_authenticated: TestClient, tmp_path: Path):
    mock_cu.return_value.calibrate_all.side_effect = ValueError("bad calibration")
    mock_get_detector.return_value = MagicMock()

    req = {
        "filess_in": [[str(tmp_path / "img0.jpg")]],
        "board_definition": {
            "squares_x": 14,
            "squares_y": 9,
            "square_length_mm": 20,
            "marker_length_mm": 15,
        },
    }
    response = client_authenticated.post("/admin/multicamera/calibration", json=req)
    assert response.status_code == 400
    assert "Failed to calibrate" in response.json()["detail"]


@patch("photobooth.routers.api_admin.multicamera.process_wigglegram_inner")
@patch("photobooth.routers.api_admin.multicamera.container")
def test_get_result_success(mock_container, mock_process, client_authenticated: TestClient, tmp_path: Path):
    # Fake acquisition service
    mock_container.acquisition_service.wait_for_multicam_files.return_value = [tmp_path / "img0.jpg"]

    # Fake processed images
    img = Image.new("RGB", (100, 100))
    mock_process.return_value = [img]

    response = client_authenticated.get("/admin/multicamera/result")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"


@patch("photobooth.routers.api_admin.multicamera.process_wigglegram_inner", side_effect=RuntimeError("fail"))
@patch("photobooth.routers.api_admin.multicamera.container")
def test_get_result_failure(mock_container, mock_process, client_authenticated: TestClient):
    mock_container.acquisition_service.wait_for_multicam_files.return_value = []

    response = client_authenticated.get("/admin/multicamera/result")
    assert response.status_code == 500
    assert "something went wrong" in response.json()["detail"]
