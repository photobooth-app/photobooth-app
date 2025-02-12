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
        assert len(context.images) == len(self.collage_merge_definition)  # ensure numbers are right

        for index, _definition in enumerate(self.collage_merge_definition):
            logger.debug(_definition)
            _image = context.images[index]
            _image = ImageOps.fit(_image, (_definition.width, _definition.height), method=Image.Resampling.LANCZOS)  # or contain?
            _image, offset_x, offset_y = __class__.rotate(_image, _definition.rotate)

            # _image needs to have an alpha channel, otherwise paste with mask=_image fails.
            # above rotate always converts to RGBA consistently now to ensure paste nevers fails.
            context.canvas.paste(_image, (_definition.pos_x - offset_x, _definition.pos_y - offset_y), _image)

        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__

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
