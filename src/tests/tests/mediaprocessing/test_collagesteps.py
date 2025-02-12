"""
Testing Mediaprocessing collage
"""

import logging

import pytest
from PIL import Image

from photobooth.services.config.groups.actions import CollageMergeDefinition
from photobooth.services.mediaprocessing.context import CollageContext
from photobooth.services.mediaprocessing.pipeline import Pipeline
from photobooth.services.mediaprocessing.steps.collage import MergeCollageStep

logger = logging.getLogger(name=None)


def test_collage_stage():
    canvas = Image.new("RGBA", (1500, 1500), color=None)
    images: list[Image.Image] = [
        Image.open("src/tests/assets/input.jpg"),
        Image.open("src/tests/assets/input.jpg"),
        Image.open("src/tests/assets/input.jpg"),
    ]
    collage_merge_definition = [
        CollageMergeDefinition(rotate=5),
        CollageMergeDefinition(pos_x=800, rotate=-5),
        CollageMergeDefinition(pos_y=800),
    ]

    context = CollageContext(canvas, images)
    steps = [MergeCollageStep(collage_merge_definition)]
    pipeline = Pipeline[CollageContext](*steps)
    pipeline(context)
    stage_output = context.canvas

    assert canvas.mode == "RGBA"
    assert canvas.mode == stage_output.mode
    assert canvas.size == stage_output.size
    assert canvas is stage_output  # actually we merged all on canvas which is also output


def test_collage_stage_definition_not_matching_with_no_captured():
    # 2 captures vs. 3 required per definition
    canvas = Image.new("RGBA", (1500, 1500), color=None)
    images: list[Image.Image] = [
        Image.open("src/tests/assets/input.jpg"),
        Image.open("src/tests/assets/input.jpg"),
    ]
    collage_merge_definition = [
        CollageMergeDefinition(rotate=5),
        CollageMergeDefinition(pos_x=800, rotate=-5),
        CollageMergeDefinition(pos_y=800),
    ]
    with pytest.raises(AssertionError):
        context = CollageContext(canvas, images)
        steps = [MergeCollageStep(collage_merge_definition)]
        pipeline = Pipeline[CollageContext](*steps)
        pipeline(context)
