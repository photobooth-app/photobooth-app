import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

import cv2
import numpy as np
from PIL import Image

from ...helper import filename_str_time
from .base import CalibrationBase, PersistableDataclass

logger = logging.getLogger(__name__)

DEBUG_TMP = True


@dataclass
class CalDataAlign(PersistableDataclass):
    H: cv2.typing.MatLike


class SimpleCalibrationUtil(CalibrationBase[CalDataAlign]):
    """Specialized calibration manager."""

    FILE_PREFIX = "simple"  # override if desired

    def __init__(self):
        super().__init__()

        self.__crop_area: tuple[int, int, int, int] | None = None  # x, y, w, h, computed on first use and then cached

    def load_calibration_data(self, dir: Path) -> None:
        """Load all calibration data from disk."""
        super()._load_calibration_data(dir, CalDataAlign)

    def calibrate_all(self, cameras: list[list[Path]], ref_idx: int, detector: cv2.aruco.CharucoDetector):
        """Calibrate all cameras against the reference camera.
        cameras[0] is all images for camera 0 listed.

        WARNING: The images are not allowed to be flipped or the marker recognition fails!
        # https://stackoverflow.com/questions/71126639/aruco-markers-are-not-detected

        """
        caldataalign: list[CalDataAlign] = []

        calibration_datetime = datetime.now().astimezone().strftime("%x-%X")
        w, h = Image.open(cameras[0][0]).size  # assume all images same size, this is only very basic sanity check

        for cam_idx, img_files in enumerate(cameras):
            H = self.__calibrate_pair(cameras[ref_idx], img_files, ref_idx, cam_idx, detector)

            caldataalign.append(CalDataAlign(H=H, calibration_datetime=calibration_datetime, img_width=w, img_height=h))

            logger.info(f"Calculated homography for camera {cam_idx} relative to {ref_idx}")

        # when completed, save to instance variable
        assert len(caldataalign) == len(cameras)
        self._caldataalign = caldataalign

    def align_all(self, files_in: list[Path], out_dir: Path, crop: bool = True) -> list[Path]:
        """align all images, while 1 image per camera, sorted by the index"""

        assert self._caldataalign, "No calibration data loaded. You need to load the data first or calibrate."
        files_out: list[Path] = []

        # sanity check input images match calibration data
        input_image_size = Image.open(files_in[0]).size
        caldataalign = self._caldataalign[0]
        assert caldataalign

        if input_image_size != (caldataalign.img_width, caldataalign.img_height):
            logger.warning(
                f"Image size {input_image_size[0]}x{input_image_size[1]} does not match calibration "
                "size {caldataalign.img_width}x{caldataalign.img_height}"
            )
            return files_in  # return unmodified files

        for cam_idx, img_file in enumerate(files_in):
            try:
                caldataalign = self._caldataalign[cam_idx]
            except IndexError as exc:
                raise RuntimeError(f"Calibration data for camera {cam_idx} not found. Is the data loaded?") from exc

            proc_img = cv2.imread(str(img_file))
            proc_img = self.__align_to_reference(caldataalign.H, proc_img)

            if DEBUG_TMP:
                cv2.imwrite(f"tmp/aligned_{cam_idx}.jpg", proc_img)
            if crop:
                if not self.__crop_area:
                    self.__crop_area = self.__compute_common_crop()

                proc_img = self.__crop_to_common_intersect(proc_img, self.__crop_area)

                if DEBUG_TMP:
                    cv2.imwrite(f"tmp/cropped_{cam_idx}.jpg", proc_img)

            out_filepath = Path(
                NamedTemporaryFile(
                    mode="wb",
                    delete=False,
                    dir=out_dir,
                    prefix=f"{filename_str_time()}_multicam_aligned_",
                    suffix=".jpg",
                ).name
            )
            cv2.imwrite(str(out_filepath), proc_img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            files_out.append(out_filepath)

        logger.info(f"Aligned {len(files_out)} files to {self.__crop_area} crop area.")

        return files_out

    def reset_calibration_data(self):
        """Reset calibration data."""
        super().reset_calibration_data()

        self.__crop_area = None
        logger.info("Reset calibration data")

    @staticmethod
    def __aggregate_detections(image_files: list[Path], detector: cv2.aruco.CharucoDetector) -> tuple[np.ndarray, np.ndarray]:
        """
        Aggregate detections from multiple images of the same camera.
        Returns stacked corners and IDs.
        """
        all_corners, all_ids = [], []
        for i, fname in enumerate(image_files):
            img = cv2.imread(str(fname), cv2.IMREAD_GRAYSCALE)

            if img is None:
                raise ValueError(f"Failed to read image {fname}")

            # some preprocessing for charuco detection improved.
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img = clahe.apply(img)

            if DEBUG_TMP:
                out_path = f"tmp/{fname.stem}_{i}_detector_in.png"
                cv2.imwrite(str(out_path), img)

            corners, ids, _, _ = detector.detectBoard(img)

            if ids is not None and corners is not None:
                all_corners.append(corners)
                all_ids.append(ids)

                # --- Debug visualization using OpenCV helper ---
                if DEBUG_TMP:
                    debug_img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                    cv2.aruco.drawDetectedCornersCharuco(debug_img, corners, ids)
                    out_path = f"tmp/{fname.stem}_{i}_detected.png"
                    cv2.imwrite(str(out_path), debug_img)

        if not all_ids:
            raise ValueError("No ChArUco corners detected in any image.")

        return np.vstack(all_corners), np.vstack(all_ids)

    @staticmethod
    def __compute_homography(ref_corners: np.ndarray, ref_ids: np.ndarray, cur_corners: np.ndarray, cur_ids: np.ndarray) -> np.ndarray:
        """Compute homography between reference and current camera using common ChArUco IDs."""
        ref_map = {id_: corner for id_, corner in zip(ref_ids.flatten(), ref_corners, strict=False)}
        cur_map = {id_: corner for id_, corner in zip(cur_ids.flatten(), cur_corners, strict=False)}

        common_ids = np.intersect1d(list(ref_map.keys()), list(cur_map.keys()))
        if len(common_ids) < 4:
            raise ValueError("Not enough common ChArUco corners to compute homography.")

        src_pts = np.array([cur_map[cid] for cid in common_ids]).reshape(-1, 1, 2)
        dst_pts = np.array([ref_map[cid] for cid in common_ids]).reshape(-1, 1, 2)
        H, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC)  # could return None if fails

        if H is None:
            raise ValueError("Homography computation failed")

        return H

    def __calibrate_pair(
        self,
        ref_images: list[Path],
        cur_images: list[Path],
        ref_idx: int,
        cur_idx: int,
        detector: cv2.aruco.CharucoDetector,
    ) -> np.ndarray:
        """Calibrate one camera against the reference and save homography."""
        if cur_idx == ref_idx:
            return np.eye(3)  # Identity homography for reference camera

        ref_corners, ref_ids = self.__aggregate_detections(ref_images, detector)
        cur_corners, cur_ids = self.__aggregate_detections(cur_images, detector)

        H = self.__compute_homography(ref_corners, ref_ids, cur_corners, cur_ids)

        return H

    def __compute_common_crop(self) -> tuple[int, int, int, int]:
        """
        Compute the common overlapping crop region across all cameras.
        Returns (x1, y1, x2, y2) in reference frame coordinates.
        """
        # Assume all images same size
        w, h = self._caldataalign[0].img_width, self._caldataalign[0].img_height

        # Define corners of the image (top-left, top-right, bottom-right, bottom-left)
        img_corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32).reshape(-1, 1, 2)

        # Initialize intersection bounds with the reference image itself
        x_min, y_min, x_max, y_max = 0, 0, w, h

        for cal in self._caldataalign:
            H = cal.H
            warped = cv2.perspectiveTransform(img_corners, H).reshape(-1, 2)

            # Get bounding box of this warped quadrilateral
            max_lefts = max(warped[0, 0], warped[3, 0])
            max_tops = max(warped[0, 1], warped[1, 1])
            min_rights = min(warped[1, 0], warped[2, 0])
            min_bottoms = min(warped[2, 1], warped[3, 1])

            # Update intersection
            x_min = max(x_min, int(np.floor(max_lefts)))
            y_min = max(y_min, int(np.floor(max_tops)))
            x_max = min(x_max, int(np.ceil(min_rights)))
            y_max = min(y_max, int(np.ceil(min_bottoms)))

        if x_max <= x_min or y_max <= y_min:
            raise ValueError("No common overlap region found across all cameras.")

        return x_min, y_min, x_max, y_max

    @staticmethod
    def __align_to_reference(H: np.ndarray, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]

        # seems the pi cameras have bit different distortion charachteristics, maybe intrinsics cali can help in preprocessing?
        # return cv2.warpAffine(img, H[:2, :], (img.shape[1], img.shape[0]))
        return cv2.warpPerspective(img, H, (w, h), flags=cv2.INTER_CUBIC)  # dsize in (w,h) order

    @staticmethod
    def __crop_to_common_intersect(img: np.ndarray, crop: tuple[int, int, int, int]) -> np.ndarray:
        """
        Crop image to the given rectangle.

        Args:
            img: Input image.
            crop: (x1, y1, x2, y2) coordinates of the crop rectangle,
                  where (x1, y1) is top-left and (x2, y2) is bottom-right.

        Returns:
            Cropped image as np.ndarray.
        """

        x1, y1, x2, y2 = crop

        # Enusre to crop to even numbers so post processing is easier and
        # less compute intense because video codes to encoding in later steps
        # may require even numbers.

        if (x2 - x1) % 2 != 0:
            x2 -= 1
        if (y2 - y1) % 2 != 0:
            y2 -= 1

        return img[y1:y2, x1:x2]
