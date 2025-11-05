import logging
from collections.abc import Sequence
from dataclasses import dataclass

import cv2

from .base import PersistableDataclass

logger = logging.getLogger(__name__)

## This is not used, yet.
# For now we use the simple calibration routine,
# but maybe there are more advanced algorithms to process wigglegrams,
# some references for later:
# https://github.com/bdaiinstitute/spot_wrapper/blob/76e522bbb7c6351290e71b8d2acfea3aae0adb49/spot_wrapper/calibration/README.md?plain=1#L298
# https://github.com/bdaiinstitute/spot_wrapper/blob/main/spot_wrapper/calibration/calibration_util.py
# https://github.com/photobooth-app/wigglecam/blob/8bcb80e417ea5078b6bc95c277f399ad94dda1b0/wigglecam/connector/calibrator.py


@dataclass
class CalibrationDataIntrinsics(PersistableDataclass):
    mtx: cv2.typing.MatLike
    dist: cv2.typing.MatLike
    rvecs: Sequence[cv2.typing.MatLike]
    tvecs: Sequence[cv2.typing.MatLike]

    err: float


@dataclass
class CalibrationDataExtrinsics(PersistableDataclass):
    err: float
    Kl: cv2.typing.MatLike
    Dl: cv2.typing.MatLike
    Kr: cv2.typing.MatLike
    Dr: cv2.typing.MatLike
    R: cv2.typing.MatLike
    T: cv2.typing.MatLike
    E: cv2.typing.MatLike
    F: cv2.typing.MatLike

    # M: cv2.typing.MatLike
