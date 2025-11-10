import logging
from pathlib import Path

import cv2
from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel

from ... import TMP_PATH
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

    try:
        sanitized_input = [[filenames_sanitize(file_in) for file_in in files_in] for files_in in filess_in]

        detector = get_detector()

        cu = SimpleCalibrationUtil()
        cu.calibrate_all(cameras=sanitized_input, ref_idx=0, detector=detector)
        cu.save_calibration_data(CALIBRATION_DATA_PATH)

    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Failed to calibrate, error {exc}") from exc
    else:
        container.reload()
        return {"ok": True}


@router.get("/result")
def api_get_result():
    file_out = Path(TMP_PATH, "wiggledemo.gif")
    try:
        files_to_process = container.acquisition_service.wait_for_multicam_files()
        files_backend_postprocessed = container.acquisition_service.postprocess_multicam_set(files_in=files_to_process, out_dir=Path(TMP_PATH))

        multicamera_images: list[Image.Image] = [Image.open(image_in) for image_in in files_backend_postprocessed]
        for img in multicamera_images:
            img.thumbnail((500, 500))

        multicamera_images = multicamera_images + list(reversed(multicamera_images[1 : len(multicamera_images) - 1]))
        multicamera_images[0].save(
            file_out,
            format="gif",
            save_all=True,
            append_images=multicamera_images[1:] if len(multicamera_images) > 1 else [],
            optimize=True,
            duration=125,
            loop=0,  # loop forever
        )

        return FileResponse(path=file_out, media_type="image/gif", content_disposition_type="inline")
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"something went wrong, Exception: {exc}") from exc
