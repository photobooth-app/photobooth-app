import cv2
import cv2.aruco as aruco


def get_detector(size: tuple[int, int] = (9, 6), square_length: float = 30, marker_length: float = 22) -> cv2.aruco.CharucoDetector:
    aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_250)

    charuco_board = aruco.CharucoBoard(size=size, squareLength=square_length, markerLength=marker_length, dictionary=aruco_dict)
    detector_params = cv2.aruco.CharucoParameters()
    detector_params.minMarkers = 0
    detector_params.tryRefineMarkers = True
    charuco_detector = cv2.aruco.CharucoDetector(charuco_board, detector_params)

    return charuco_detector
