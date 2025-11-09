import logging

import cv2
import cv2.aruco as aruco
import numpy as np

logger = logging.getLogger(__name__)


def get_detector(size: tuple[int, int] = (14, 9), square_length: float = 20.0, marker_length: float = 15.0) -> cv2.aruco.CharucoDetector:
    """Size: (SquaresX, SquaresY), while X is left-right (width/columns) and Y top-bottom (height,rows)"""
    aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_250)

    charuco_board = aruco.CharucoBoard(size=size, squareLength=square_length, markerLength=marker_length, dictionary=aruco_dict)
    detector_params = cv2.aruco.CharucoParameters()
    detector_params.minMarkers = 0
    detector_params.tryRefineMarkers = True
    charuco_detector = cv2.aruco.CharucoDetector(charuco_board, detector_params)

    return charuco_detector


def generate_board(size: tuple[int, int] = (14, 9), square_length_mm: float = 20.0, marker_length_mm: float = 15.0) -> np.ndarray:
    """Size: (SquaresX/Cols, SquaresY/Rows), while X is left-right and Y is top-bottom"""
    dpi: int = 200
    squares_x_cols = size[0]
    squares_y_rows = size[1]

    # Convert to pixels
    width_mm = squares_x_cols * square_length_mm
    height_mm = squares_y_rows * square_length_mm
    width_px = int(width_mm / 25.4 * dpi)
    height_px = int(height_mm / 25.4 * dpi)

    aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_1000)
    board = cv2.aruco.CharucoBoard((squares_x_cols, squares_y_rows), square_length_mm, marker_length_mm, aruco_dict)
    board_img = board.generateImage((width_px, height_px), marginSize=40, borderBits=1)

    # Add axis labels with cv2.putText
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.75
    thickness = 2
    color = (0, 0, 0)  # black text

    # X-axis label (top left)
    cv2.putText(
        board_img,
        "Squares X / Cols ->   Other dir is Squares Y / Rows. !If the text is mirrored in calibration images, calibration fails!",
        (15, 25),
        font,
        font_scale,
        color,
        thickness,
        cv2.LINE_AA,
    )
    cv2.putText(
        board_img,
        f"photobooth-app.org | {squares_x_cols}x{squares_y_rows} | Square Length: {square_length_mm} | Marker Length: {marker_length_mm}"
        " | AruCo DICT_4X4",
        (15, height_px - 15),
        font,
        font_scale,
        color,
        thickness,
        cv2.LINE_AA,
    )

    return board_img
