import logging
from pathlib import Path

import cv2
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from ...container import container
from ...services.backends.wigglecam import CALIBRATION_DATA_PATH
from ...utils.helper import filenames_sanitize
from ...utils.multistereo_calibration.algorithms.simple import SimpleCalibrationUtil
from ...utils.multistereo_calibration.charuco_board import generate_board, get_detector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/multicamera", tags=["admin", "multicamera"])


class CharucoRequest(BaseModel):
    squares_x: int = 14
    squares_y: int = 9
    square_length_mm: float = 20
    marker_length_mm: float = 15


@router.get("/calibration")
def api_get_calibration_stats():
    raise NotImplementedError


@router.post("/calibration/charuco")
def api_get_calibration_generate_charucoboard(req: CharucoRequest):
    try:
        board_arr = generate_board((req.squares_x, req.squares_y), square_length_mm=req.square_length_mm, marker_length_mm=req.marker_length_mm)

        # Encode as PNG in memory
        success, png_bytes = cv2.imencode(".png", board_arr)
        if not success:
            raise RuntimeError("Failed to encode board image")

        # Return as HTTP response
        return Response(content=png_bytes.tobytes(), media_type="image/png")

    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate board: {exc}") from exc


@router.delete("/calibration")
def api_delete_calibration_delete():
    cu = SimpleCalibrationUtil()
    cu.delete_calibration_data(CALIBRATION_DATA_PATH)

    container.reload()

    return {"ok": True}


@router.post("/calibration")
def api_post_calibrate_all(filess_in: list[list[Path]]):
    """Post files to calculate a new calibration, save it and reload services to apply the calibration.

    filess_in = [
        [Path("./tmp/calib_test_in/input_0.jpg"),...],  # camera 0
        [Path("./tmp/calib_test_in/input_1.jpg"),...],  # camera 1
        [Path("./tmp/calib_test_in/input_2.jpg"),...],  # ...
        [Path("./tmp/calib_test_in/input_3.jpg"),...],
    ]
    """

    # print(filess_in)
    try:
        sanitized_input = [[filenames_sanitize(file_in) for file_in in files_in] for files_in in filess_in]
        # print(sanitized_input)
        detector = get_detector()

        # sanitized_input = [
        #     [Path("./tmp/calib_test_in/input_0.jpg")],  # camera 0
        #     [Path("./tmp/calib_test_in/input_1.jpg")],  # camera 1
        #     [Path("./tmp/calib_test_in/input_2.jpg")],  # ...
        #     [Path("./tmp/calib_test_in/input_3.jpg")],
        # ]

        cu = SimpleCalibrationUtil()
        cu.calibrate_all(cameras=sanitized_input, ref_idx=0, detector=detector)
        cu.save_calibration_data(CALIBRATION_DATA_PATH)

    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Failed to calibrate, error {exc}") from exc
    else:
        container.reload()
        return {"ok": True}
