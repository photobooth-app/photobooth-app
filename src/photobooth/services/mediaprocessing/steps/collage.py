from __future__ import annotations

import logging

from PIL import Image, ImageOps

from ...config.models.models import CollageMergeDefinition
from ..context import CollageContext
from ..pipeline import NextStep, PipelineStep

logger = logging.getLogger(__name__)


class MergeCollageStep(PipelineStep):
    def __init__(self, collage_merge_definition: list[CollageMergeDefinition]) -> None:
        self.collage_merge_definition = collage_merge_definition

    def __call__(self, context: CollageContext, next_step: NextStep) -> None:
        assert context.canvas.mode == "RGBA"  # ensure were always operating on img with alpha channel

        layer_pairs = zip(self.collage_merge_definition, context.images, strict=True)  # strict also ensures numbers are right (same len)

        for merge_def, img in sorted(layer_pairs, key=lambda p: p[0].pos_z, reverse=False):
            logger.debug(merge_def)

            img = ImageOps.fit(img, (merge_def.width, merge_def.height), method=Image.Resampling.LANCZOS)
            img, offset_x, offset_y = __class__.rotate(img, merge_def.rotate)

            # _image needs to have an alpha channel, otherwise paste with mask=_image fails.
            # above rotate always converts to RGBA consistently now to ensure paste nevers fails.
            context.canvas.paste(img, (merge_def.pos_x - offset_x, merge_def.pos_y - offset_y), img)

        next_step(context)

    @staticmethod
    def rotate(image: Image.Image, angle: int = 0, expand: bool = True) -> tuple[Image.Image, int, int]:
        if angle == 0:
            # quick return, but also convert to RGBA for consistency reason in following processing
            return image.convert("RGBA"), 0, 0

        _rotated_image = image.convert("RGBA").rotate(
            angle=angle,
            expand=expand,
            resample=Image.Resampling.BICUBIC,
        )  # pos values = counter clockwise

        # https://github.com/python-pillow/Pillow/issues/4556
        offset_x = int(_rotated_image.width / 2 - image.width / 2)
        offset_y = int(_rotated_image.height / 2 - image.height / 2)

        return _rotated_image, offset_x, offset_y
