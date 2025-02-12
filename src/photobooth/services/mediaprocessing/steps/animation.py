from __future__ import annotations

import logging

from PIL import Image, ImageOps

from ..context import AnimationContext
from ..pipeline import NextStep, PipelineStep

logger = logging.getLogger(__name__)


class AlignSizesStep(PipelineStep):
    def __init__(self, canvas_size: tuple[int, int]) -> None:
        self.canvas_size = canvas_size  # W x H

    def __call__(self, context: AnimationContext, next_step: NextStep) -> None:
        sequenced_images: list[Image.Image] = []

        for _image in context.images:
            sequenced_images.append(ImageOps.fit(_image, self.canvas_size, method=Image.Resampling.LANCZOS))  # or contain?

        # update all after finished and unset var to help garbage collection
        context.images = sequenced_images
        del sequenced_images

        next_step(context)

    def __repr__(self) -> str:
        return self.__class__.__name__
