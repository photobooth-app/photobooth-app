from __future__ import annotations

import logging

import cv2
import numpy as np
from cv2.typing import MatLike
from PIL import Image, ImageDraw

from ..context import MulticameraContext
from ..pipeline import NextStep, PipelineStep

logger = logging.getLogger(__name__)


class AutoPivotPointStep(PipelineStep):
    def __init__(self) -> None: ...

    def __call__(self, context: MulticameraContext, next_step: NextStep) -> None:
        def center_of_image(img: Image.Image) -> tuple[int, int]:
            w, h = img.size

            return (w // 2, h // 2)

        # def ... todoOTHERMETHOD
        # https://docs.opencv.org/4.x/d4/d8c/tutorial_py_shi_tomasi.html

        # update result in context.
        context.base_img_pt_0 = center_of_image(context.images[0])

        logger.info(f"{context.base_img_pt_0=}")

        next_step(context)


class OffsetPerOpticalFlowStep(PipelineStep):
    """Align next_img to prev_img using optical flow of pivot point."""

    def __init__(self) -> None: ...

    def __call__(self, context: MulticameraContext, next_step: NextStep) -> None:
        # aligned_images: list[Image.Image] = []
        relative_offsets: list[tuple[int, int]] = []
        assert context.base_img_pt_0

        base_img = context.images[0]
        gray_base_arr = self.preprocess(base_img)

        pt_base = context.base_img_pt_0
        pt_base_arr = np.array([[pt_base]], dtype=np.float32)

        visL = gray_base_arr.copy()
        cv2.drawMarker(visL, (int(pt_base[0]), int(pt_base[1])), (0, 255, 0), cv2.MARKER_TILTED_CROSS, 20, 2)
        cv2.imwrite("tmp/markers_0.png", visL)

        # Chain-align each subsequent image to the ref img one
        relative_offsets.append((0, 0))  # base has no offset to apply later
        # base_img.save(f"tmp/recentered_img_{i}.jpg")  # actually no offset on base.

        for idx, next_img in enumerate(context.images[1:], start=1):
            gray_next_arr = self.preprocess(next_img)

            # p1 is in absolute units
            p1, st, err = cv2.calcOpticalFlowPyrLK(
                gray_base_arr,
                gray_next_arr,
                pt_base_arr,
                None,  # type: ignore[arg-type]
                winSize=(21, 21),
                maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
            )

            if st[0][0] != 1:
                logger.warning("Korrespondenz konnte nicht gefunden werden, using image center as fallback")
                pt_next = pt_base
            else:
                pt_next = tuple(p1[0, 0])

            offset = (int(pt_next[0] - pt_base[0]), int(pt_next[1] - pt_base[1]))

            relative_offsets.append(offset)

            # Marker einzeichnen
            visR = gray_next_arr.copy()
            cv2.drawMarker(visR, (int(pt_next[0]), int(pt_next[1])), (0, 255, 0), cv2.MARKER_TILTED_CROSS, 20, 2)
            cv2.imwrite(f"tmp/markers_{idx}.png", visR)

        context.relative_offsets = relative_offsets

        next_step(context)

    @staticmethod
    def preprocess(img: Image.Image) -> MatLike:
        img_arr = np.array(img)
        gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
        # eq = cv2.equalizeHist(gray)
        eq = gray
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
