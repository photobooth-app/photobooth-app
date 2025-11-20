import logging
from pathlib import Path

import cv2
from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ... import TMP_PATH
from ...container import container
from ...services.backends.wigglecam import CALIBRATION_DATA_PATH
from ...services.config.groups.actions import MulticameraProcessing
from ...services.mediaprocessing.processes import process_wigglegram_inner
from ...utils.helper import filenames_sanitize
from ...utils.multistereo_calibration.algorithms.simple import SimpleCalibrationUtil
from ...utils.multistereo_calibration.charuco_board import generate_board, get_detector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/multicamera", tags=["admin", "multicamera"])


class CharucoBoardDefinition(BaseModel):
    squares_x: int = 14
    squares_y: int = 9
    square_length_mm: float = 20
    marker_length_mm: float = 15


class CalibrationRequest(BaseModel):
    filess_in: list[list[Path]]
    board_definition: CharucoBoardDefinition


@router.get("/calibration")
def api_get_calibration_stats():
    raise NotImplementedError


@router.post("/calibration/charuco")
def api_get_calibration_generate_charucoboard(req: CharucoBoardDefinition):
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

    return {"ok": True}


@router.post("/calibration")
def api_post_calibrate_all(req: CalibrationRequest):
    """Post files to calculate a new calibration, save it and reload services to apply the calibration.

    filess_in = [
        [Path("./tmp/calib_test_in/input_0.jpg"),...],  # camera 0
        [Path("./tmp/calib_test_in/input_1.jpg"),...],  # camera 1
        [Path("./tmp/calib_test_in/input_2.jpg"),...],  # ...
        [Path("./tmp/calib_test_in/input_3.jpg"),...],
    ]
    """

    logger.info(f"Trying to detect board definition {req.board_definition} in {len(req.filess_in)} images.")

    try:
        sanitized_input = [[filenames_sanitize(file_in) for file_in in files_in] for files_in in req.filess_in]

        detector = get_detector(
            (req.board_definition.squares_x, req.board_definition.squares_y),
            req.board_definition.square_length_mm,
            req.board_definition.marker_length_mm,
        )

        cu = SimpleCalibrationUtil()
        cu.calibrate_all(cameras=sanitized_input, ref_idx=0, detector=detector)
        cu.save_calibration_data(CALIBRATION_DATA_PATH)

    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Failed to calibrate, error {exc}") from exc
    else:
        return {"ok": True}


@router.get("/result")
def api_get_result():
    file_out = Path(TMP_PATH, "wiggledemo.webp")
    try:
        config = MulticameraProcessing()
        files_to_process = container.acquisition_service.wait_for_multicam_files()
        images_processed = process_wigglegram_inner(files_in=files_to_process, config=config, preview=False)

        for img in images_processed:
            img.thumbnail((500, 500))

        images_processed = images_processed + list(reversed(images_processed[1 : len(images_processed) - 1]))
        images_processed[0].save(
            file_out,
            format=None,
            save_all=True,
            append_images=images_processed[1:] if len(images_processed) > 1 else [],
            optimize=True,
            duration=config.duration,
            loop=0,  # loop forever
        )

        return FileResponse(path=file_out, media_type="image/webp", content_disposition_type="inline")
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"something went wrong, Exception: {exc}") from exc
