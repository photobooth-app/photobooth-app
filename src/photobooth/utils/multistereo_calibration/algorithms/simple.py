import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .base import CalibrationBase, PersistableDataclass

logger = logging.getLogger(__name__)

DEBUG_TMP = False


@dataclass
class CalDataAlign(PersistableDataclass):
    H: cv2.typing.MatLike


class SimpleCalibrationUtil(CalibrationBase[CalDataAlign]):
    """Specialized calibration manager."""

    FILE_PREFIX = "simple"  # override if desired

    def __init__(self):
        super().__init__()

    def load_calibration_data(self, dir: Path) -> None:
        """Load all calibration data from disk."""
        super()._load_calibration_data(dir, CalDataAlign)

    def identity_all(self, number_cameras: int, img_width: int, img_height: int):
        """Set identity caldata so output will not be modified at all but useful in testing"""
        self._caldataalign = [CalDataAlign(f"dummytime_cam_{i}", img_width, img_height, H=np.eye(3)) for i in range(number_cameras)]

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

    def align_all(self, images: list[Image.Image], crop: bool) -> list[Image.Image]:
        """align all images, while 1 image per camera, sorted by the index"""

        assert self._caldataalign, "No calibration data loaded. You need to load the data first or calibrate."
        assert len(images) >= 2, "need at least 2 images to align"

        # all images have same dimension
        img_size = images[0].size
        if any(img.size != img_size for img in images[1:]):
            logger.warning("Not all images share the same dimensions")
            raise ValueError("Not all images share the same dimensions")

        # sanity check existing calibration data is applicable to input images (need at least same aspect ratio, but could be resized)
        try:
            for caldataalign, image in zip(self._caldataalign, images, strict=True):
                # Compute aspect ratios
                img_ratio = image.width / image.height
                cal_ratio = caldataalign.img_width / caldataalign.img_height

                # Allow small floating-point tolerance
                if not np.isclose(img_ratio, cal_ratio, rtol=1e-3, atol=1e-3):
                    raise ValueError(
                        f"Image aspect ratio {image.width}x{image.height} "
                        f"({img_ratio:.4f}) does not match calibration ratio "
                        f"{caldataalign.img_width}x{caldataalign.img_height} "
                        f"({cal_ratio:.4f})"
                    )
        except ValueError as exc:
            logger.warning(f"number of images and calibration data do not align - you need to recalibrate, error {exc}")
            raise

        proc_images_out = []
        crop_area = None
        for cam_idx, (caldataalign, image) in enumerate(zip(self._caldataalign, images, strict=True)):
            # print(cam_idx, caldataalign, image)

            H_rescaled = self.__rescale_H(caldataalign.H, (caldataalign.img_width, caldataalign.img_height), image.size)
            proc_img = self.__align_to_reference(H_rescaled, image)

            if DEBUG_TMP:
                proc_img.save(f"tmp/aligned_{cam_idx}.jpg")

            if crop:
                # cache once per run; assumes all images are same size though
                if not crop_area:
                    crop_area = self.__compute_common_crop(img_size)

                proc_img = self.__crop_to_common_intersect(proc_img, crop_area)

                if DEBUG_TMP:
                    proc_img.save(f"tmp/cropped_{cam_idx}.jpg")

            proc_images_out.append(proc_img)

        logger.info(f"Aligned {len(proc_images_out)} files to {crop_area} crop area.")

        return proc_images_out

    def reset_calibration_data(self):
        """Reset calibration data."""
        super().reset_calibration_data()

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

    @staticmethod
    def __rescale_H(H, orig_size, new_size):
        w0, h0 = orig_size
        w1, h1 = new_size

        sx, sy = w1 / w0, h1 / h0

        S = np.array([[sx, 0, 0], [0, sy, 0], [0, 0, 1]], dtype=float)
        S_inv = np.array([[1 / sx, 0, 0], [0, 1 / sy, 0], [0, 0, 1]], dtype=float)

        H_rescaled = S @ H @ S_inv
        return H_rescaled

    def __compute_common_crop(self, image_size: tuple[int, int]) -> tuple[int, int, int, int]:
        """
        Compute the common overlapping crop region across all cameras.
        Returns (x1, y1, x2, y2) in reference frame coordinates.
        """
        # Assume all images same size
        w, h = image_size[0], image_size[1]

        # Define corners of the image (top-left, top-right, bottom-right, bottom-left)
        img_corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32).reshape(-1, 1, 2)

        # Initialize intersection bounds with the reference image itself
        x_min, y_min, x_max, y_max = 0, 0, w, h

        for cal in self._caldataalign:
            H_rescaled = self.__rescale_H(cal.H, (cal.img_width, cal.img_height), image_size)
            warped = cv2.perspectiveTransform(img_corners, H_rescaled).reshape(-1, 2)

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
    def __align_to_reference(H: np.ndarray, image: Image.Image) -> Image.Image:
        img_arr = np.array(image)
        # img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR) # only geometric manipulation, can skip color conversion
        img_arr_warped = cv2.warpPerspective(img_arr, H, image.size, flags=cv2.INTER_CUBIC)
        # warped_rgb = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img_arr_warped)

    @staticmethod
    def __crop_to_common_intersect(img: Image.Image, crop: tuple[int, int, int, int]) -> Image.Image:
        """
        Crop a Pillow image to the given rectangle.

        Args:
            img (Image.Image): Input PIL image.
            crop (tuple[int, int, int, int]): (x1, y1, x2, y2) coordinates of the crop rectangle,
                                              where (x1, y1) is top-left and (x2, y2) is bottom-right.

        Returns:
            Image.Image: Cropped PIL image.
        """
        x1, y1, x2, y2 = crop

        # Ensure even width/height for downstream video encoding compatibility
        if (x2 - x1) % 2 != 0:
            x2 -= 1
        if (y2 - y1) % 2 != 0:
            y2 -= 1

        # Pillow crop uses (left, upper, right, lower)
        return img.crop((x1, y1, x2, y2))
