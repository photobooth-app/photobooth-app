"""
Testing Mediaprocessing collage
"""

import logging

from PIL import Image

from photobooth.services.mediaprocessing.context import AnimationContext
from photobooth.services.mediaprocessing.pipeline import Pipeline
from photobooth.services.mediaprocessing.steps.animation import AlignSizesStep

logger = logging.getLogger(name=None)


def test_align_sizes_stage():
    canvas_size = (400, 400)  # w, h
    images: list[Image.Image] = [
        Image.open("src/tests/assets/input.jpg"),
        Image.open("src/tests/assets/input.jpg"),
        Image.open("src/tests/assets/input.jpg"),
    ]

    context = AnimationContext(images)
    steps = [AlignSizesStep(canvas_size)]
    pipeline = Pipeline[AnimationContext](*steps)
    pipeline(context)
    out_images = context.images

    # ensure input was bigger width/height
    for image in images:
        assert image.width > canvas_size[0]
        assert image.height > canvas_size[1]

    assert len(images) == len(out_images)
    for out_image in out_images:
        assert out_image.width <= canvas_size[0]
        assert out_image.height <= canvas_size[1]
