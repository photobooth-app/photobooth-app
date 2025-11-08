import logging
from pathlib import Path

import cv2
import numpy as np
import pytest

from photobooth.utils.multistereo_calibration.algorithms.simple import SimpleCalibrationUtil
from photobooth.utils.multistereo_calibration.charuco_board import generate_board, get_detector

logger = logging.getLogger(__name__)


@pytest.fixture
def dummy_charuco_images(tmp_path: Path):
    ref_board_img = generate_board((7, 5))

    image_paths: list[list[Path]] = []
    for cam_id in range(4):
        board_img = ref_board_img.copy()

        # --- Apply random offset + rotation ---
        h, w = board_img.shape[:2]
        center = (w // 2, h // 2)

        # Small random rotation in degrees
        angle = np.random.uniform(-5, 5)  # ±5°
        # Small random translation
        tx = np.random.randint(-20, 20)
        ty = np.random.randint(-20, 20)

        # Build affine transform
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        M[0, 2] += tx
        M[1, 2] += ty

        if cam_id != 0:
            warped = cv2.warpAffine(board_img, M, (w, h))
        else:
            warped = board_img

        image_path = tmp_path / f"charuco_cam{cam_id}.jpg"
        cv2.imwrite(str(image_path), warped)
        image_paths.append([image_path])

    return image_paths


def test_generate_board_even(tmp_path: Path):
    board = generate_board((8, 10))

    cv2.imwrite(f"{tmp_path}/charuco_board_generated.jpg", board)

    detector = get_detector((8, 10), square_length=40, marker_length=20)
    corners, ids, _, _ = detector.detectBoard(board)
    assert len(corners) == (8 - 1) * (10 - 1)
    assert len(ids) == (8 - 1) * (10 - 1)


def test_generate_board_odd(tmp_path: Path):
    board = generate_board((15, 9))

    cv2.imwrite(f"{tmp_path}/charuco_board_generated.jpg", board)

    detector = get_detector((15, 9), square_length=40, marker_length=20)
    corners, ids, _, _ = detector.detectBoard(board)
    assert len(corners) == (15 - 1) * (9 - 1)
    assert len(ids) == (15 - 1) * (9 - 1)


def test_calibration_util_calibrate(tmp_path: Path, dummy_charuco_images):
    cameras = dummy_charuco_images
    detector = get_detector((7, 5), square_length=40, marker_length=20)
    calibrator = SimpleCalibrationUtil()
    calibrator.calibrate_all(cameras, 0, detector)
    calibrator.save_calibration_data(tmp_path)
    calibrator.reset_calibration_data()

    calibrator.load_calibration_data(tmp_path)
    calibrator.align_all([item[0] for item in cameras], tmp_path)

    calibrator2 = SimpleCalibrationUtil()
    calibrator2.load_calibration_data(tmp_path)
    calibrator2.align_all([item[0] for item in cameras], tmp_path)
