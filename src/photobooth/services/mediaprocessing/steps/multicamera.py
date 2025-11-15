from __future__ import annotations

import logging

import cv2
import numpy as np
import numpy.typing as npt
from cv2.typing import MatLike
from PIL import Image, ImageDraw

from ....utils.multistereo_calibration.algorithms.simple import SimpleCalibrationUtil
from ...backends.wigglecam import CALIBRATION_DATA_PATH
from ..context import MulticameraContext
from ..pipeline import NextStep, PipelineStep

logger = logging.getLogger(__name__)


class AutoPivotPointStep(PipelineStep):
    def __init__(self) -> None: ...

    def __call__(self, context: MulticameraContext, next_step: NextStep) -> None:
        def find_good_features(img: Image.Image, roi_center: tuple[int, int], roi_size: int = 100, max_corners: int = 20) -> npt.NDArray[np.float32]:
            """
            Find good Shi-Tomasi corners in a ROI centered at roi_center.
            Returns an array of shape (N,1,2) with float32 coordinates,
            ready to be passed into cv2.calcOpticalFlowPyrLK.
            """
            img_arr = np.array(img)
            h, w = img_arr.shape[:2]
            cx, cy = roi_center

            # define ROI bounds (clamped to image size)
            x1, y1 = max(cx - roi_size, 0), max(cy - roi_size, 0)
            x2, y2 = min(cx + roi_size, w - 1), min(cy + roi_size, h - 1)

            roi = img_arr[y1:y2, x1:x2]
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

            corners = cv2.goodFeaturesToTrack(gray_roi, maxCorners=max_corners, qualityLevel=0.01, minDistance=5)

            if corners is None:
                # fallback: just return the ROI center
                return np.array([[[cx, cy]]], dtype=np.float32)

            # shift ROI coords back to full image
            corners[:, 0, 0] += x1
            corners[:, 0, 1] += y1

            # --- Debug visualization ---
            debug_img = img_arr.copy()
            # draw ROI rectangle
            cv2.rectangle(debug_img, (x1, y1), (x2, y2), (255, 255, 0), 1)
            # draw all corners
            for c in corners:
                x, y = c.ravel()
                cv2.circle(debug_img, (int(x), int(y)), 4, (0, 255, 0), 1)
            # mark ROI center
            cv2.drawMarker(debug_img, (cx, cy), (255, 0, 0), markerType=cv2.MARKER_CROSS, markerSize=10, thickness=1)

            cv2.imwrite("tmp/corners.jpg", debug_img)
            # ----------------------------

            return corners.astype(np.float32)

        def upper_third_of_image(img: Image.Image) -> tuple[int, int]:
            w, h = img.size

            return (w // 2, int(h // 2.5))

        # update result in context.
        context.good_features_to_track = find_good_features(context.images[0], upper_third_of_image(context.images[0]))

        # logger.info(f"{context.good_features_to_track=}")

        next_step(context)


class OffsetPerOpticalFlowStep(PipelineStep):
    """Align next_img to prev_img using optical flow of multiple pivot points."""

    def __init__(self) -> None: ...

    def __call__(self, context: MulticameraContext, next_step: NextStep) -> None:
        relative_offsets: list[tuple[int, int]] = []
        assert context.good_features_to_track is not None

        gray_base_arr = self.preprocess(context.images[0])
        base_pts = context.good_features_to_track

        # visualize base points
        visL = cv2.cvtColor(gray_base_arr, cv2.COLOR_GRAY2BGR)
        for p in base_pts:
            x, y = p.ravel()
            cv2.circle(visL, (int(x), int(y)), 3, (0, 255, 0), 1)
        cv2.imwrite("tmp/markers_0.png", visL)

        # base has no offset
        relative_offsets.append((0, 0))

        # track across subsequent images
        for idx, next_img in enumerate(context.images[1:], start=1):
            gray_next_arr = self.preprocess(next_img)

            next_pts, st, err = cv2.calcOpticalFlowPyrLK(
                gray_base_arr,
                gray_next_arr,
                base_pts,  # always refer to the first image
                None,  # type: ignore[arg-type]
                winSize=(21, 21),
                maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
            )

            # filter valid points
            good_new = next_pts[st == 1]
            good_old = base_pts[st == 1]

            if len(good_new) == 0:
                logger.warning("No correspondences found, using image center as fallback")
                h, w = gray_next_arr.shape[:2]
                pt_next_mean = (w // 2, h // 2)
                pt_base_mean = (w // 2, h // 2)
            else:
                # average positions for stability
                pt_next_mean = tuple(np.mean(good_new, axis=0))
                pt_base_mean = tuple(np.mean(good_old, axis=0))

            offset = (int(pt_next_mean[0] - pt_base_mean[0]), int(pt_next_mean[1] - pt_base_mean[1]))
            relative_offsets.append(offset)

            # visualize tracked points
            visR = cv2.cvtColor(gray_next_arr, cv2.COLOR_GRAY2BGR)
            for p in good_new:
                x, y = p.ravel()
                cv2.circle(visR, (int(x), int(y)), 3, (0, 255, 0), 1)
            cv2.drawMarker(visR, (int(pt_next_mean[0]), int(pt_next_mean[1])), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 20, 2)
            cv2.imwrite(f"tmp/markers_{idx}.png", visR)

        context.relative_offsets = relative_offsets
        next_step(context)

    @staticmethod
    def preprocess(img: Image.Image) -> MatLike:
        img_arr = np.array(img)
        gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
        eq = gray  # or cv2.equalizeHist(gray)
        blur = cv2.GaussianBlur(eq, (5, 5), 0)
        return blur


class CropCommonAreaStep(PipelineStep):
    """Align next_img to prev_img using optical flow of pivot point."""

    def __init__(self) -> None: ...

    def __call__(self, context: MulticameraContext, next_step: NextStep) -> None:
        assert len(context.images) >= 2, "need at least 2 images!"
        assert context.relative_offsets is not None, "need relative offsets to be calculated in prior step!"
        assert len(context.relative_offsets) == len(context.images), "offset len doesn't match images len"

        w, h = context.images[0].size
        assert all(img.size == (w, h) for img in context.images), f"Images differ in size; expected {w=}, {h=}"

        # Step 1: compute bounding boxes in base image coordinates, the left/upper coords are correct after this routine
        # Right/Lower need to be corrected using new_canvas_h/w because the width/height is avail only after complete processing
        boxes = []

        root_offset_x = min(dx for dx, _ in context.relative_offsets)
        root_offset_y = min(dy for _, dy in context.relative_offsets)
        logger.info(f"{root_offset_x=} {root_offset_y=}")

        for _, (_, (dx, dy)) in enumerate(zip(context.images, context.relative_offsets, strict=True)):
            left = +dx - root_offset_x
            upper = +dy - root_offset_y
            right = left + w
            lower = upper + h

            box = (left, upper, right, lower)
            boxes.append(box)

        # Step 2: get the new canvas w/h (smallest intersection of all images), it's used to calc right/lower in step3 correctly.
        x_min = max(b[0] for b in boxes)  # left
        y_min = max(b[1] for b in boxes)  # upper
        x_max = min(b[2] for b in boxes)  # right
        y_max = min(b[3] for b in boxes)  # lower
        new_canvas_w = x_max - x_min
        new_canvas_h = y_max - y_min

        logger.info(f"new canvas w={new_canvas_w}, h={new_canvas_h}")

        if new_canvas_w <= 0 or new_canvas_h <= 0:
            raise ValueError("No overlapping region between images")

        # Step 3: crop each image in local coordinates
        cropped_images: list[Image.Image] = []
        for idx, (img, (dx, dy)) in enumerate(zip(context.images, context.relative_offsets, strict=True)):
            left = +dx - root_offset_x
            upper = +dy - root_offset_y
            right = left + new_canvas_w
            lower = upper + new_canvas_h
            logger.info(f"numbers {idx}: {root_offset_x=} {root_offset_y=} {dx=} {dy=}")
            logger.info(f"crop-bounds {idx}: {left=} {upper=} {right=} {lower=}")
            img_crppd = img.crop((left, upper, right, lower))
            logger.info(f"res img {idx}: size orig: {img.size}, after: {img_crppd.size}")
            img_crppd.save(f"tmp/cropped_{idx}.jpg")
            self.draw_bbox(img, (left, upper, right, lower)).save(f"tmp/bbox-corrected_{idx}.jpg")
            cropped_images.append(img_crppd)

        context.images = cropped_images
        del cropped_images

        next_step(context)

    @staticmethod
    def draw_bbox(img: Image.Image, box: tuple[int, int, int, int], color="red", width=3) -> Image.Image:
        """
        Draw a bounding box on a copy of the image.
        box = (x_min, y_min, x_max, y_max) in image coordinates
        """
        img_copy = img.copy()
        draw = ImageDraw.Draw(img_copy)
        draw.rectangle(box, outline=color, width=width)
        return img_copy

    # @staticmethod
    # def recenter_image_chops(img, offset: tuple[int, int]):
    #     dx, dy = offset
    #     return ImageChops.offset(img, -dx, -dy)


class AlignAsPerCalibrationStep(PipelineStep):
    """Calibration is part of the backends and currently only for the multicam, so we can keep it here.
    Maybe in future we can also support calibrate intrinisics of picamera to remove lens distortions and
    improve stereo calibration

    The backends only use a subset of the calibration util: load and align, so only these are exposed.
    Calibration routine and saving is done in the multicam-tool which is actually living in the api backend endpoints."""

    def __init__(self, crop: bool = True) -> None:
        self._cal_util = SimpleCalibrationUtil()
        self._calibration_data_path = CALIBRATION_DATA_PATH
        self._crop = crop

        try:
            self._cal_util.load_calibration_data(self._calibration_data_path)
            logger.info("Calibration data loaded successfully")
        except Exception as exc:
            logger.warning(f"No valid multicam calibration loaded, the results may suffer. Error: {exc}")

    def __call__(self, context: MulticameraContext, next_step: NextStep) -> None:
        try:
            context.images = self._cal_util.align_all(context.images, crop=self._crop)
        except Exception as exc:
            logger.warning(f"Error aligning multicam images according to existing calibration. Please rerun multicamera calibration. Error: {exc}")

        next_step(context)
