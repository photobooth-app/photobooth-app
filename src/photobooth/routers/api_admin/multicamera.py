import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from ...container import container
from ...services.backends.wigglecam import CALIBRATION_DATA_PATH
from ...utils.helper import filenames_sanitize
from ...utils.multistereo_calibration.algorithms.simple import SimpleCalibrationUtil
from ...utils.multistereo_calibration.detector import get_detector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/multicamera", tags=["admin", "multicamera"])


@router.get("/calibration")
def api_get_calibration_stats():
    raise NotImplementedError


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
