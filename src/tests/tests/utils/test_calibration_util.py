import logging
from pathlib import Path

import cv2
import numpy as np
import pytest

from photobooth.utils.multistereo_calibration.algorithms.simple import SimpleCalibrationUtil
from photobooth.utils.multistereo_calibration.detector import get_detector

logger = logging.getLogger(__name__)


@pytest.fixture
def dummy_charuco_images(tmp_path: Path):
    # Define ChArUco board parameters
    squares_x = 5
    squares_y = 7
    square_length = 40
    marker_length = 20
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    board = cv2.aruco.CharucoBoard((squares_x, squares_y), square_length, marker_length, dictionary)

    image_paths = {}
    for cam_id in range(4):
        board_img = board.generateImage((800, 600), marginSize=10, borderBits=1)

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

        warped = cv2.warpAffine(board_img, M, (w, h))

        image_path = tmp_path / f"charuco_cam{cam_id}.jpg"
        cv2.imwrite(str(image_path), warped)
        image_paths[cam_id] = [image_path]

    return image_paths


def test_calibration_util_calibrate(tmp_path: Path, dummy_charuco_images):
    cameras = dummy_charuco_images
    detector = get_detector((5, 7), square_length=40, marker_length=20)
    calibrator = SimpleCalibrationUtil()
    calibrator.calibrate_all(cameras, 0, detector)
    calibrator.save_calibration_data(tmp_path)
    calibrator.reset_calibration_data()

    calibrator.load_calibration_data(tmp_path)
    calibrator.align_all([item[0] for item in cameras.values()], tmp_path)

    calibrator2 = SimpleCalibrationUtil()
    calibrator2.load_calibration_data(tmp_path)
    calibrator2.align_all([item[0] for item in cameras.values()], tmp_path)
